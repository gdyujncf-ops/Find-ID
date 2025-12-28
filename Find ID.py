# coding: utf-8
__version__ = (1, 0, 0)

# module: Find ID
# meta developer: NFTkarma (адаптированно)

import io
import logging
from datetime import datetime
from telethon.errors import RPCError
from telethon.tl.types import Message, User
from .. import loader, utils

logger = logging.getLogger(__name__)


@loader.tds
class Gift(loader.Module):
    """
    Модуль переписан для команды .id
    Команда .id возвращает:
      - Имя
      - Юзернейм
      - Айди
      - Дата (приблизительная) создания аккаунта (День Месяц Год)
    """

    strings = {
        # Название модуля сделано простым текстом "Find id" без кастомных эмодзи,
        # чтобы модуль корректно загружался.
        "name": "Find id",
        "usage": "<emoji document_id=5433875443306481415>🏆</emoji><b> Успех</b>\n"
                 "<b>Использование:</b>\n"
                 "<code>.id</code> - информация о себе\n"
                 "<code>.id @username</code> - информация о пользователе по юзернейму\n"
                 "<code>.id &lt;user_id&gt;</code> - информация по id\n"
                 "<code>.id</code> (в ответ на сообщение) - информация о том, на кого отвечают",
        "getting_info": "<emoji document_id=5199733815106354300>💎</emoji><b> Успех</b>\n🔎 <b>Получаю информацию...</b>",
        "no_user": "<emoji document_id=5199485574586581548>💠</emoji><b> Успех</b>\n⚠️ <b>Пользователь не найден.</b>",
        "error": "<emoji document_id=5197688070643661681>🆔</emoji><b> Успех</b>\n😵 <b>Произошла ошибка:</b> <code>{}</code>",
        "result": "<emoji document_id=5197228921459850148>🎁</emoji><b> Успех</b>\n"
                  "{name_emoji} <b>Имя:</b> {name}\n"
                  "{username_emoji} <b>Юзернейм:</b> {username}\n"
                  "{id_emoji} <b>Айди:</b> <code>{uid}</code>\n"
                  "{date_emoji} <b>Дата (приблизительная) создания:</b> <code>{created}</code>",
        "unknown": "<emoji document_id=5197228921459850148>🏆</emoji><b> Успех</b>\nНеизвестно"
    }

    async def client_ready(self, client, db):
        self.client = client
        self.db = db

    def _format_date(self, dt: datetime):
        try:
            return dt.strftime("%d %B %Y")
        except Exception:
            return self.strings["unknown"]

    def _wrap_blockquote(self, text: str) -> str:
        # Оборачивает весь текст в HTML-цитирование
        return f"<blockquote>{text}</blockquote>"

    async def _get_entity_from_arg_or_reply(self, message: Message):
        """
        Попытка определить целевого пользователя по аргументу команды,
        по ответу на сообщение или по отправителю самого сообщения.
        Возвращает Telethon entity или None.
        """
        args = utils.get_args_raw(message)
        # reply check
        try:
            reply = await message.get_reply_message()
        except Exception:
            reply = None

        if args:
            target = args.strip()
            # try numeric id
            if target.isdigit():
                try:
                    return await self.client.get_entity(int(target))
                except Exception:
                    pass
            # try username or mention
            try:
                return await self.client.get_entity(target)
            except Exception:
                # try with @
                if not target.startswith("@"):
                    try:
                        return await self.client.get_entity("@" + target)
                    except Exception:
                        pass
            return None
        elif reply:
            # from reply message get sender
            try:
                sender = await reply.get_sender()
                return sender
            except Exception:
                return None
        else:
            # default: self (автор команды)
            try:
                return await message.get_sender()
            except Exception:
                return None

    @loader.command(ru_doc="Показать id и информацию о пользователе")
    async def id(self, message: Message):
        """
        .id [username|id] (или ответ на сообщение)
        Вернет: Имя, Юзернейм, Айди, и примерную дату создания (по самой ранней доступной фотографии профиля).
        Примечание: точной даты создания аккаунта API не предоставляет, поэтому дата будет
        основана на самой ранней фотографии профиля (если есть) — это приближение.
        """
        # Отправляем сообщение о получении информации (в цитате)
        status = await utils.answer(message, self._wrap_blockquote(self.strings["getting_info"]))
        try:
            entity = await self._get_entity_from_arg_or_reply(message)
            if not entity:
                await status.edit(self._wrap_blockquote(self.strings["no_user"]))
                return

            # удостоверимся, что entity — это User
            if not isinstance(entity, User):
                # попытка получить user-entity из общего объекта
                try:
                    entity = await self.client.get_entity(entity)
                except Exception:
                    await status.edit(self._wrap_blockquote(self.strings["no_user"]))
                    return

            # Собираем данные
            raw_full_name = (" ".join(filter(None, [getattr(entity, "first_name", "") or "", getattr(entity, "last_name", "") or ""]))).strip()
            full_name = utils.escape_html(raw_full_name) or self.strings["unknown"]

            username_val = getattr(entity, "username", None)
            username_display = ("@" + username_val) if username_val else self.strings["unknown"]
            username_display_escaped = utils.escape_html(username_display) if username_val else self.strings["unknown"]

            user_id = getattr(entity, "id", self.strings["unknown"])

            # Попытка оценить дату "создания" аккаунта через самую раннюю фотографию профиля.
            created_str = self.strings["unknown"]
            try:
                photos = await self.client.get_profile_photos(entity, limit=200)
                if photos and len(photos) > 0:
                    # берем самую раннюю загруженную фотографию (последний элемент)
                    earliest = photos[-1]
                    # Telethon Photo имеет поле .date (datetime) — используем его, если есть
                    dt = getattr(earliest, "date", None)
                    if isinstance(dt, datetime):
                        created_str = self._format_date(dt)
                    else:
                        created_str = self.strings["unknown"]
                else:
                    created_str = self.strings["unknown"]
            except RPCError as e:
                logger.debug("RPCError while getting profile photos: %s", e)
                created_str = self.strings["unknown"]
            except Exception as e:
                logger.debug("Error while getting profile photos: %s", e)
                created_str = self.strings["unknown"]

            # Emoji (по одному на каждое поле) — вставлены в формате custom emoji (document_id)
            name_emoji = "<emoji document_id=5199742486645325689>💎</emoji>"
            username_emoji = "<emoji document_id=5197180478523719604>💠</emoji>"
            id_emoji = "<emoji document_id=5197195523794157505>🆔</emoji>"
            date_emoji = "<emoji document_id=5199485574586581548>🏆</emoji>"

            # Формируем текст результата (строка "Успех" уже в strings["result"], после неё — данные)
            result_text = self.strings["result"].format(
                name_emoji=name_emoji,
                username_emoji=username_emoji,
                id_emoji=id_emoji,
                date_emoji=date_emoji,
                name=f"<code>{full_name}</code>" if full_name != self.strings["unknown"] else f"<b>{self.strings['unknown']}</b>",
                username=f"<code>{username_display_escaped}</code>" if username_val else f"<b>{self.strings['unknown']}</b>",
                uid=user_id,
                created=created_str
            )

            # Оборачиваем в цитату и отправляем
            await status.edit(self._wrap_blockquote(result_text), parse_mode="html")
        except Exception as e:
            logger.exception("Error in .id command: %s", e)
            await status.edit(self._wrap_blockquote(self.strings["error"].format(utils.escape_html(str(e)))), parse_mode="html")