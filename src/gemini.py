"""
Gemini AI client untuk Oline bot.
Mengelola percakapan dengan Gemini API termasuk function calling,
memori pengguna, dan riwayat percakapan.
"""

import json
import logging
import os
from typing import Any, Optional

import google.generativeai as genai

from src.kv import get_history, get_memory, save_history, save_memory
from src.personas import (
    MEMORY_INJECTION_TEMPLATE,
    NO_MEMORY_NOTE,
    OLINE_SYSTEM_PROMPT,
)
from src.tools import TOOL_DECLARATIONS, TOOL_EXECUTORS

logger = logging.getLogger(__name__)

# Konfigurasi Gemini API
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.0-flash"


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


def _build_system_prompt(memory: str) -> str:
    """Build system prompt lengkap dengan memori pengguna."""
    prompt = OLINE_SYSTEM_PROMPT

    if memory:
        prompt += MEMORY_INJECTION_TEMPLATE.format(memory=memory)
    else:
        prompt += NO_MEMORY_NOTE

    return prompt


def _format_history_for_gemini(history: list[dict]) -> list[dict]:
    """
    Convert riwayat percakapan dari KV ke format Gemini contents.
    Format KV: [{"role": "user|model", "text": "..."}]
    Format Gemini: [{"role": "user|model", "parts": [{"text": "..."}]}]
    """
    contents = []
    for msg in history:
        role = msg.get("role", "user")
        text = msg.get("text", "")
        if text:
            contents.append({
                "role": role,
                "parts": [{"text": text}],
            })
    return contents


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
        # Remap 'text' parameter for save_journal_entry
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


async def chat_with_oline(chat_id: int, user_message: str) -> str:
    """
    Main function untuk chat dengan Oline.
    Mengelola seluruh alur: memori, riwayat, function calling, dan respons.

    Args:
        chat_id: Telegram chat ID pengguna
        user_message: Pesan teks dari pengguna

    Returns:
        Respons teks dari Oline
    """
    try:
        _configure_gemini()

        # 1. Ambil memori dan riwayat
        memory = await get_memory(chat_id)
        history = await get_history(chat_id)

        # 2. Build system prompt
        system_prompt = _build_system_prompt(memory)

        # 3. Buat model dengan tools
        tools = _build_tools()
        model = genai.GenerativeModel(
            GEMINI_MODEL,
            system_instruction=system_prompt,
            tools=tools,
        )

        # 4. Siapkan conversation contents
        contents = _format_history_for_gemini(history)
        contents.append({
            "role": "user",
            "parts": [{"text": user_message}],
        })

        # 5. Generate response (mungkin function call)
        response = model.generate_content(contents)

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
                        genai.types.Part.from_function_response(
                            name=fc.name,
                            response=result,
                        )
                    )

            if not has_function_call:
                break

            # Tambahkan response model + function results ke contents
            contents.append(candidate.content)
            contents.append(
                genai.types.Content(
                    role="function",
                    parts=function_responses,
                )
            )

            # Generate lagi dengan function results
            response = model.generate_content(contents)

        # 7. Extract final text response
        bot_response = ""
        if response.candidates:
            for part in response.candidates[0].content.parts:
                if hasattr(part, "text") and part.text:
                    bot_response += part.text

        if not bot_response:
            bot_response = "hmm, aku lagi error nih. coba lagi nanti ya 😅"

        # 8. Update riwayat percakapan
        history.append({"role": "user", "text": user_message})
        history.append({"role": "model", "text": bot_response})
        await save_history(chat_id, history)

        # 9. Update memori (setiap 5 pesan untuk efisiensi)
        if len(history) % 10 == 0:  # Setiap 5 pertukaran (10 pesan)
            await _update_memory(chat_id, user_message, bot_response, memory)

        return bot_response

    except Exception as e:
        logger.error("Error in chat_with_oline: %s", str(e))
        return "aduh maaf, aku lagi ada masalah teknis nih 😅 coba lagi nanti ya!"
