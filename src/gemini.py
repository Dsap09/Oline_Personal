"""
Gemini AI client untuk Oline bot.
Mengelola percakapan dengan Gemini API termasuk function calling,
memori pengguna, dan riwayat percakapan.
"""

import asyncio
import json
import logging
import os
from typing import Any, Optional

import google.ai.generativelanguage as glm
import google.generativeai as genai

from src.kv import get_history, get_memory, save_history, save_memory, save_usage
from src.personas import (
    MEMORY_INJECTION_TEMPLATE,
    OLINE_SYSTEM_PROMPT,
)
from src.tools import TOOL_DECLARATIONS, TOOL_EXECUTORS

logger = logging.getLogger(__name__)

# Konfigurasi Gemini API
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")


def _configure_gemini():
    """Konfigurasi Gemini API client."""
    if not GEMINI_API_KEY:
        raise ValueError(
            "GEMINI_API_KEY environment variable is not set. "
            "Cannot initialize Gemini client."
        )
    genai.configure(api_key=GEMINI_API_KEY)


def _build_tools() -> list[genai.types.Tool]:
    """Build Gemini Tool objects dari deklarasi."""
    function_declarations = []
    for tool_decl in TOOL_DECLARATIONS:
        function_declarations.append(
            genai.types.FunctionDeclaration(
                name=tool_decl["name"],
                description=tool_decl["description"],
                parameters=tool_decl["parameters"],
            )
        )
    return [genai.types.Tool(function_declarations=function_declarations)]


def _build_system_prompt(memory: str, user_name: str = "Teman") -> str:
    """Build system prompt lengkap dengan nama pengguna & memori."""
    if user_name and user_name not in ("Anonim", "Teman"):
        user_info = f"- Nama Pengguna: {user_name} (Sapa pengguna secara ramah dan santai dengan nama {user_name})."
    else:
        user_info = "- Nama Pengguna belum diketahui secara pasti. Jika pengguna memberi tahu namanya (misal: 'namaku Doni'), ingat nama tersebut."

    prompt = OLINE_SYSTEM_PROMPT.format(user_info_section=user_info)

    if memory:
        prompt += MEMORY_INJECTION_TEMPLATE.format(memory=memory)

    return prompt


def _format_history_for_gemini(history: list[dict]) -> list[dict]:
    """
    Convert dan bersihkan riwayat percakapan dari KV ke format Gemini contents.
    Memastikan riwayat SELALU berselang-seling antara 'user' dan 'model'.
    Jika ada 2 pesan berurutan dengan peran sama, teks digabungkan.
    """
    if not history:
        return []

    cleaned = []
    for msg in history:
        role = msg.get("role", "user")
        text = msg.get("text", "").strip()

        if not text:
            continue

        # Normalisasi role
        role = "user" if role != "model" else "model"

        if cleaned and cleaned[-1]["role"] == role:
            # Penggabungan teks jika role berturut-turut sama
            cleaned[-1]["parts"][0]["text"] += f"\n{text}"
        else:
            cleaned.append({
                "role": role,
                "parts": [{"text": text}],
            })

    # Jika item terakhir di cleaned adalah 'user', hapus agar pesan user baru yang akan di-append
    # tidak menghasilkan 2 'user' berturut-turut
    if cleaned and cleaned[-1]["role"] == "user":
        cleaned.pop()

    return cleaned


async def _execute_function_call(
    function_call: Any, chat_id: int
) -> dict[str, Any]:
    """
    Execute sebuah function call dari Gemini dan return hasilnya.
    """
    func_name = function_call.name
    func_args = dict(function_call.args) if function_call.args else {}

    logger.info("Executing function call: %s with args: %s", func_name, func_args)

    executor = TOOL_EXECUTORS.get(func_name)
    if not executor:
        return {"error": f"Unknown function: {func_name}"}

    # Untuk journal functions, inject chat_id
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
        _configure_gemini()
        model = genai.GenerativeModel(GEMINI_MODEL)

        memory_prompt = f"""Kamu adalah asisten yang bertugas merangkum informasi penting dari percakapan.

Memori sebelumnya:
{current_memory if current_memory else "(Belum ada)"}

Percakapan baru:
User: {user_message}
Bot: {bot_response}

Tugas: Perbarui ringkasan memori dengan menambahkan informasi baru yang penting (seperti nama pengguna, hobi, kejadian penting, preferensi). Jaga ringkasan tetap singkat (maksimal 300 kata). Jika tidak ada informasi baru yang relevan, kembalikan memori sebelumnya tanpa perubahan.

Format output: langsung tuliskan ringkasan memori tanpa prefix atau label."""

        response = model.generate_content(memory_prompt)
        if response and response.text:
            await save_memory(chat_id, response.text.strip())
    except Exception as e:
        logger.error("Failed to update memory: %s", str(e))


# Model kandidat untuk rotasi & fallback otomatis jika salah satu model terkena 429/quota limit
DEFAULT_MODEL_CANDIDATES = [
    "gemini-1.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-pro",
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
    system_prompt: str, tools: list[genai.types.Tool], contents: Any
) -> tuple[Any, str, int]:
    """
    Memanggil model.generate_content dengan rotasi & fallback otomatis antar model kandidat.
    Jika satu model terkena 429 / Rate Limit / Quota Exceeded, otomatis mencoba model cadangan berikutnya.
    Returns: (response, used_model_name, total_tokens)
    """
    candidates = _get_model_candidates()
    last_exception = None

    for model_name in candidates:
        try:
            model = genai.GenerativeModel(
                model_name,
                system_instruction=system_prompt,
                tools=tools,
            )
            response = await asyncio.to_thread(model.generate_content, contents)
            logger.info("Successfully generated content using model: %s", model_name)

            # Ekstrak usage_metadata untuk tracking token
            total_tokens = 0
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                meta = response.usage_metadata
                total_tokens = getattr(meta, "total_token_count", 0) or (
                    getattr(meta, "prompt_token_count", 0)
                    + getattr(meta, "candidates_token_count", 0)
                )

            # Fallback estimasi jika API tidak mengembalikan token count (misal 1 token ≈ 4 karakter)
            if total_tokens == 0:
                prompt_len = sum(len(str(c)) for c in contents) if isinstance(contents, list) else len(str(contents))
                resp_len = len(response.text) if hasattr(response, "text") and response.text else 100
                total_tokens = max(15, (prompt_len + resp_len) // 4)

            return response, model_name, total_tokens
        except Exception as e:
            err_msg = str(e).lower()
            last_exception = e
            is_rate_limit = (
                "429" in err_msg
                or "resourceexhausted" in err_msg
                or "quota exceeded" in err_msg
                or "rate limit" in err_msg
            )
            if is_rate_limit:
                logger.warning(
                    "Model %s failed with rate limit/quota (%s). Falling back to next model candidate...",
                    model_name,
                    str(e),
                )
                continue
            else:
                raise e

    if last_exception:
        raise last_exception
    raise RuntimeError("All Gemini model candidates failed.")


async def chat_with_oline(
    chat_id: int, user_message: str, user_name: str = "Teman"
) -> str:
    """
    Main function untuk chat dengan Oline.
    Mengelola seluruh alur: memori, riwayat, function calling, dan respons.

    Args:
        chat_id: Telegram chat ID pengguna
        user_message: Pesan teks dari pengguna
        user_name: Nama pengguna dari profil Telegram

    Returns:
        Respons teks dari Oline
    """
    try:
        _configure_gemini()

        # 1. Ambil memori dan riwayat
        memory = await get_memory(chat_id)
        history = await get_history(chat_id)

        # 2. Build system prompt dengan user_name
        system_prompt = _build_system_prompt(memory, user_name=user_name)

        # 3. Buat tools
        tools = _build_tools()

        # 4. Siapkan conversation contents
        contents = _format_history_for_gemini(history)
        contents.append({
            "role": "user",
            "parts": [{"text": user_message}],
        })

        # 5. Generate response (mungkin function call) dengan automatic fallback
        response, used_model, tokens_used = await _generate_content_with_fallback(
            system_prompt, tools, contents
        )

        # Track token usage
        total_tokens_session = tokens_used

        # 6. Handle function calling loop
        max_iterations = 3  # Batas safety untuk loop function calling
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            # Cek apakah ada function call
            if not response.candidates:
                break

            candidate = response.candidates[0]

            # Cek function call di parts
            has_function_call = False
            function_responses = []

            for part in candidate.content.parts:
                if hasattr(part, "function_call") and part.function_call:
                    has_function_call = True
                    fc = part.function_call

                    # Execute function
                    result = await _execute_function_call(fc, chat_id)

                    function_responses.append(
                        glm.Part(
                            function_response=glm.FunctionResponse(
                                name=fc.name,
                                response=result,
                            )
                        )
                    )

            if not has_function_call:
                break

            # Tambahkan response model + function results ke contents (dengan role='user')
            contents.append(candidate.content)
            contents.append(
                glm.Content(
                    role="user",
                    parts=function_responses,
                )
            )

            # Generate lagi dengan function results
            response, used_model, tokens_used = await _generate_content_with_fallback(
                system_prompt, tools, contents
            )
            total_tokens_session += tokens_used

        # 7. Extract final text response
        bot_response = ""
        if response.candidates:
            for part in response.candidates[0].content.parts:
                if hasattr(part, "text") and part.text:
                    bot_response += part.text

        if not bot_response:
            bot_response = "hmm, aku lagi error nih. coba lagi nanti ya 😅"

        # 8. Update riwayat percakapan (hanya jika sukses dan tidak error)
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
        return "aduh maaf, aku lagi ada masalah teknis nih 😅 coba lagi nanti ya!"
