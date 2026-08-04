"""
Gemini AI client untuk Oline bot.
Mengelola percakapan dengan Gemini API (menggunakan google-genai SDK)
termasuk function calling, memori pengguna, dan riwayat percakapan.
"""

import asyncio
from datetime import datetime
import json
import logging
import os
from typing import Any, Optional

from google import genai
from google.genai import types

from src.kv import get_history, get_memory, save_history, save_memory, save_usage
from src.personas import (
    MEMORY_INJECTION_TEMPLATE,
    OLINE_SYSTEM_PROMPT,
)
from src.tools import TOOL_EXECUTORS, get_tools_for_intent
from src.utils import format_date_indonesian

logger = logging.getLogger(__name__)

# Konfigurasi Gemini API
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-lite-latest")


def _get_client() -> genai.Client:
    """Mengembalikan instance Client dari google-genai SDK."""
    if not GEMINI_API_KEY:
        raise ValueError(
            "GEMINI_API_KEY environment variable is not set. "
            "Cannot initialize Gemini client."
        )
    return genai.Client(api_key=GEMINI_API_KEY)


def _build_tools(tool_declarations: list[dict]) -> Optional[list[types.Tool]]:
    """Build google-genai Tool objects dari daftar deklarasi terfilter."""
    if not tool_declarations:
        return None
    function_declarations = []
    for tool_decl in tool_declarations:
        function_declarations.append(
            types.FunctionDeclaration(
                name=tool_decl["name"],
                description=tool_decl["description"],
                parameters=tool_decl["parameters"],
            )
        )
    return [types.Tool(function_declarations=function_declarations)]


def _build_system_prompt(memory: str, user_name: str = "Teman") -> str:
    """Build system prompt lengkap dengan nama pengguna & memori."""
    if user_name and user_name not in ("Anonim", "Teman"):
        user_info = f"- Nama Pengguna: {user_name} (Sapa pengguna secara ramah dan santai dengan nama {user_name})."
    else:
        user_info = "- Nama Pengguna belum diketahui secara pasti. Jika pengguna memberi tahu namanya (misal: 'namaku Doni'), ingat nama tersebut."

    now_date = datetime.now().strftime("%Y-%m-%d")
    now_str = format_date_indonesian(now_date)
    user_info += f"\n- Tanggal & Waktu Saat Ini: {now_str} ({now_date}). Gunakan konteks tanggal ini saat menjawab pertanyaan seputar waktu, berita, atau event."

    prompt = OLINE_SYSTEM_PROMPT.format(user_info_section=user_info)

    if memory:
        prompt += MEMORY_INJECTION_TEMPLATE.format(memory=memory)

    return prompt


def _format_history_for_gemini(history: list[dict]) -> list[dict]:
    """
    Convert dan bersihkan riwayat percakapan dari KV ke format Gemini contents.
    Dibatasi maksimal 10 pesan terakhir (5 putaran percakapan) untuk efisiensi prompt.
    """
    if not history:
        return []

    # Potong maksimal 10 pesan terakhir (5 putaran)
    recent_history = history[-10:]

    cleaned = []
    for msg in recent_history:
        role = msg.get("role", "user")
        text = msg.get("text", "").strip()

        if not text:
            continue

        role = "user" if role != "model" else "model"

        if cleaned and cleaned[-1]["role"] == role:
            cleaned[-1]["parts"][0]["text"] += f"\n{text}"
        else:
            cleaned.append({
                "role": role,
                "parts": [{"text": text}],
            })

    if cleaned and cleaned[-1]["role"] == "user":
        cleaned.pop()

    return cleaned


async def _execute_function_call(
    func_name: str, func_args: dict, chat_id: int
) -> dict[str, Any]:
    """
    Execute sebuah function call dari Gemini dan return hasilnya.
    """
    logger.info("Executing function call: %s with args: %s", func_name, func_args)

    executor = TOOL_EXECUTORS.get(func_name)
    if not executor:
        return {"error": f"Unknown function: {func_name}"}

    if func_name in ("save_journal_entry", "get_journal_recap"):
        func_args["chat_id"] = chat_id
        if func_name == "save_journal_entry":
            return await executor(
                chat_id=chat_id,
                text=func_args.get("text", ""),
                date=func_args.get("date"),
            )
        else:
            return await executor(
                chat_id=chat_id,
                start_date=func_args.get("start_date"),
                end_date=func_args.get("end_date"),
            )
    elif func_name == "check_quota":
        return await executor(chat_id=chat_id)
    elif func_name == "send_voice_message":
        return await executor(chat_id=chat_id, text=func_args.get("text", ""))
    else:
        return await executor(**func_args)


async def _update_memory(
    chat_id: int, user_message: str, bot_response: str, current_memory: str
) -> None:
    """
    Update memori pengguna menggunakan Gemini.
    Hanya dipanggil sesekali untuk menjaga efisiensi.
    """
    try:
        client = _get_client()
        memory_prompt = f"""Kamu adalah asisten yang bertugas merangkum informasi penting dari percakapan.

Memori sebelumnya:
{current_memory if current_memory else "(Belum ada)"}

Percakapan baru:
User: {user_message}
Bot: {bot_response}

Tugas: Perbarui ringkasan memori dengan menambahkan informasi baru yang penting (seperti nama pengguna, hobi, kejadian penting, preferensi). Jaga ringkasan tetap singkat (maksimal 300 kata). Jika tidak ada informasi baru yang relevan, kembalikan memori sebelumnya tanpa perubahan.

Format output: langsung tuliskan ringkasan memori tanpa prefix atau label."""

        response = await asyncio.to_thread(
            client.models.generate_content,
            model=GEMINI_MODEL,
            contents=memory_prompt,
        )
        if response and response.text:
            await save_memory(chat_id, response.text.strip())
    except Exception as e:
        logger.error("Failed to update memory: %s", str(e))


# Model kandidat untuk rotasi & fallback otomatis
DEFAULT_MODEL_CANDIDATES = [
    "gemini-flash-lite-latest",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-flash-latest",
    "gemini-2.0-flash-lite",
]


def _get_model_candidates() -> list[str]:
    """Mengembalikan daftar model kandidat, memprioritaskan GEMINI_MODEL dari env jika ada."""
    configured = os.environ.get("GEMINI_MODEL", "").strip()
    candidates = list(DEFAULT_MODEL_CANDIDATES)
    if configured and configured in candidates:
        candidates.remove(configured)
        candidates.insert(0, configured)
    elif configured:
        candidates.insert(0, configured)
    return candidates


async def _generate_content_with_fallback(
    system_prompt: str,
    tools: Optional[list[types.Tool]],
    contents: Any,
    timeout_seconds: float = 8.0,
) -> tuple[Any, str, int]:
    """
    Memanggil client.models.generate_content dengan rotasi & fallback otomatis antar model kandidat.
    Dilengkapi timeout (default 8 detik) menggunakan asyncio.wait_for.
    Returns: (response, used_model_name, total_tokens)
    """
    candidates = _get_model_candidates()
    client = _get_client()
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        tools=tools if tools else None,
        temperature=0.7,
    )
    last_exception = None

    for model_name in candidates:
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    client.models.generate_content,
                    model=model_name,
                    contents=contents,
                    config=config,
                ),
                timeout=timeout_seconds,
            )
            logger.info("Successfully generated content using model: %s", model_name)

            # Token calculation
            total_tokens = 0
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                meta = response.usage_metadata
                total_tokens = getattr(meta, "total_token_count", 0) or (
                    getattr(meta, "prompt_token_count", 0)
                    + getattr(meta, "candidates_token_count", 0)
                )

            if total_tokens == 0:
                prompt_len = sum(len(str(c)) for c in contents) if isinstance(contents, list) else len(str(contents))
                resp_len = len(response.text) if hasattr(response, "text") and response.text else 100
                total_tokens = max(15, (prompt_len + resp_len) // 4)

            return response, model_name, total_tokens

        except asyncio.TimeoutError:
            logger.warning(
                "Model %s timed out after %s seconds. Falling back to next model...",
                model_name,
                timeout_seconds,
            )
            last_exception = TimeoutError(f"Model {model_name} timed out")
            continue
        except Exception as e:
            logger.warning(
                "Model %s failed (%s). Falling back to next candidate model...",
                model_name,
                str(e),
            )
            last_exception = e
            continue

    if last_exception:
        raise last_exception
    raise RuntimeError("All Gemini model candidates failed.")


async def chat_with_oline(
    chat_id: int,
    user_message: str,
    user_name: str = "Teman",
    intent: Optional[str] = None,
) -> str:
    """
    Main function untuk chat dengan Oline.
    Mengelola alur: intent tool filter, memori, riwayat, function calling, dan timeout fast/slow path.
    """
    try:
        # 1. Ambil memori dan riwayat
        memory = await get_memory(chat_id)
        history = await get_history(chat_id)

        # 2. Build system prompt
        system_prompt = _build_system_prompt(memory, user_name=user_name)

        # 2.5 Fast Path via Groq API (jika intent None dan GROQ_API_KEY diset)
        if intent is None and os.environ.get("GROQ_API_KEY", "").strip():
            try:
                from src.groq import chat_groq

                logger.info("Executing Fast Path via Groq API for chat_id: %s", chat_id)
                groq_response = await chat_groq(system_prompt, history, user_message)

                if groq_response:
                    # Update riwayat percakapan
                    history.append({"role": "user", "text": user_message})
                    history.append({"role": "model", "text": groq_response})
                    await save_history(chat_id, history)
                    return groq_response
            except Exception as e:
                logger.warning(
                    "Groq Fast Path failed (%s). Falling back to Gemini...", str(e)
                )

        # 3. Buat tools yang terfilter sesuai intent (Fast Path Gemini fallback: tools = None)

        tool_declarations = get_tools_for_intent(intent)
        tools = _build_tools(tool_declarations)

        # 4. Siapkan contents (riwayat dibatasi maks 10 pesan)
        contents = _format_history_for_gemini(history)
        contents.append({
            "role": "user",
            "parts": [{"text": user_message}],
        })

        # 5. Generate response (dengan timeout 8 detik & automatic fallback)
        response, used_model, tokens_used = await _generate_content_with_fallback(
            system_prompt, tools, contents, timeout_seconds=8.0
        )
        total_tokens_session = tokens_used

        # 6. Handle function calling loop jika ada
        max_iterations = 3
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            if not hasattr(response, "function_calls") or not response.function_calls:
                break

            if response.candidates and len(response.candidates) > 0:
                contents.append(response.candidates[0].content)

            function_responses = []
            for fc in response.function_calls:
                func_name = fc.name
                func_args = dict(fc.args) if fc.args else {}
                result = await _execute_function_call(func_name, func_args, chat_id)
                function_responses.append(
                    types.Part.from_function_response(
                        name=func_name,
                        response=result,
                    )
                )

            contents.append(
                types.Content(
                    role="user",
                    parts=function_responses,
                )
            )

            # Generate lagi dengan function results
            response, used_model, tokens_used = await _generate_content_with_fallback(
                system_prompt, tools, contents, timeout_seconds=8.0
            )
            total_tokens_session += tokens_used

        # 7. Extract final text response
        bot_response = ""
        if hasattr(response, "text") and response.text:
            bot_response = response.text
        elif response.candidates:
            for part in response.candidates[0].content.parts:
                if hasattr(part, "text") and part.text:
                    bot_response += part.text

        if not bot_response:
            bot_response = "hmm, aku lagi agak bingung nih. coba lagi nanti ya 😅"

        # 8. Update riwayat percakapan
        if "masalah teknis" not in bot_response and "error nih" not in bot_response:
            history.append({"role": "user", "text": user_message})
            history.append({"role": "model", "text": bot_response})
            await save_history(chat_id, history)

        # 9. Simpan pemakaian token ke KV
        if total_tokens_session > 0:
            await save_usage(chat_id, total_tokens_session)

        return bot_response

    except Exception as e:
        err_msg = str(e)
        logger.error("Error in chat_with_oline: %s", err_msg, exc_info=True)
        if (
            "429" in err_msg
            or "resourceexhausted" in err_msg.lower()
            or "quota exceeded" in err_msg.lower()
            or "rate limit" in err_msg.lower()
        ):
            return "aduh, trafik server AI lagi penuh banget nih 😅 coba kirim pesan lagi sebentar ya!"
        return "aduh maaf, aku lagi agak ngelag nih 😅 coba lagi nanti ya!"
