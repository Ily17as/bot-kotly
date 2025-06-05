from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from app.database.models import add_review, get_request_by_id
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

router = Router()


class ReviewFSM(StatesGroup):
    waiting_comment = State()


def make_rating_kb(request_id: int) -> InlineKeyboardMarkup:
    # 5,4,3,2,1 → чтобы красивой дугой
    buttons = [
        InlineKeyboardButton(text="⭐️"*i, callback_data=f"rate:{request_id}:{i}")
        for i in (5,4,3,2,1)
    ]
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


def skip_comment_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Пропустить ➡️", callback_data="skip_comment")]]
    )

# --- шаг 1. клиент нажал звёзды -----------------------------------
@router.callback_query(lambda c: c.data and c.data.startswith("rate:"))
async def cb_rate(query: CallbackQuery, state: FSMContext):
    _, req_id, rating = query.data.split(":")
    request_id, rating = int(req_id), int(rating)

    req = await get_request_by_id(request_id)
    if not req or req[10] != "done" or req[1] != query.from_user.id:
        return await query.answer("⛔ Оценка недоступна.", show_alert=True)

    await state.update_data(request_id=request_id,
                            master_id=req[11],
                            rating=rating)

    await query.message.edit_reply_markup()
    await query.message.answer(
        "✍️ Хотите добавить текстовый отзыв?\n"
        "Отправьте сообщение или нажмите «Пропустить ➡️».",
        reply_markup=skip_comment_kb(),
    )
    await state.set_state(ReviewFSM.waiting_comment)
    await query.answer("Спасибо за оценку!")


# --- шаг 2а. клиент отправил комментарий ---------------------------
@router.message(ReviewFSM.waiting_comment, F.text)
async def review_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    await add_review(
        data["request_id"],
        data["master_id"],
        message.from_user.id,
        data["rating"],
        message.text.strip(),
    )
    await message.answer("🙏 Спасибо за отзыв! Он уже у мастера.")
    await state.clear()


# --- шаг 2b. клиент нажал «Пропустить» -----------------------------
@router.callback_query(F.data == "skip_comment")
async def skip_comment(query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await add_review(
        data["request_id"],
        data["master_id"],
        query.from_user.id,
        data["rating"],
        None,
    )
    await query.message.edit_reply_markup()
    await query.message.answer("Спасибо! Оценка сохранена.")
    await state.clear()
    await query.answer()