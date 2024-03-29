import asyncio
import logging
import os
from datetime import datetime, timedelta

from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.errors import MessageNotModified
from pyrogram.types import Message
from translation import debloat_text, format_text

from config import CHANNEL_BACKUP, CHANNEL_TEST
from data import get_source, get_source_ids_by_api_id, get_post, set_post, get_account
from model import Post

LOG_FILENAME = rf"./logs/{datetime.now().strftime('%Y-%m-%d')}/{datetime.now().strftime('%H-%M-%S')}.log"
os.makedirs(os.path.dirname(LOG_FILENAME), exist_ok=True)
logging.basicConfig(
    format="%(asctime)s %(levelname)-5s %(funcName)-20s [%(filename)s:%(lineno)d]: %(message)s",
    encoding="utf-8",
    filename=LOG_FILENAME,
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S'
)


async def backup_single(client: Client, message: Message) -> int:
    msg_backup = await client.forward_messages(CHANNEL_BACKUP, message.chat.id, message.id)
    #   logging.info(f"Backup single", msg_backup.link)
    return msg_backup.id


async def backup_multiple(client: Client, messages: [Message]) -> int:
    msg_ids = [message.id for message in messages]
    msg_backup = (await client.forward_messages(CHANNEL_BACKUP, messages[0].chat.id, msg_ids))[0]
    #  logging.info(f"Backup multiple", msg_backup.link)
    return msg_backup.id


async def main():
    a = get_account()

    app = Client(
        name=a.name,
        api_id=a.api_id,
        api_hash=a.api_hash,
        phone_number=a.phone_number,
        #   phone_code=input(f"phone code {a.name}:"),
        password="area",
        parse_mode=ParseMode.HTML
    )

    sources = get_source_ids_by_api_id(a.api_id)  # + [CHANNEL_TEST]

    remove_sources = [CHANNEL_TEST, -1001011817559, -1001123527809]

    for channel_id in remove_sources:
        while channel_id in sources: sources.remove(channel_id)

    bf = filters.channel & filters.chat(sources) & filters.incoming & ~filters.forwarded
    mf = bf & (filters.photo | filters.video | filters.animation)

    @app.on_message(filters.text & bf)
    async def new_text(client: Client, message: Message):
        logging.info(f">>>>>> handle_text {message.chat.id, message.text.html}", )

        source = get_source(message.chat.id)

        text = await debloat_text(message, client)
        if not text:
            return

        logging.info(f"T X -single {text}", )

        backup_id = await backup_single(client, message)
        text = format_text(text, message, source, backup_id)

        if message.reply_to_message_id is not None:
            reply_post = get_post(message.chat.id, message.reply_to_message_id)
            if reply_post is None:
                reply_id = None
            else:
                reply_id = reply_post.message_id
        else:
            reply_id = None

        logging.info(f"send New Text {client.name}")
        msg = await client.send_message(source.destination, text, disable_web_page_preview=True)

        set_post(Post(
            msg.chat.id,
            msg.id,
            message.chat.id,
            message.id,
            backup_id,
            reply_id,
            text
        ))

    @app.on_edited_message(filters.text & bf)
    async def edit_text(client: Client, message: Message):
        logging.info(f">>>>>> edit_text {message.chat.id, message.text.html}", )

        if message.date < (datetime.now() - timedelta(weeks=1)):
            return

        await asyncio.sleep(60)
        post = get_post(message.chat.id, message.id)

        if post is None:
            await new_text(client, message)
            return

        source = get_source(message.chat.id)

        text = await debloat_text(message, client)
        if not text:
            return

        logging.info(f"edit text::: {post}", )

        text = format_text(text, message, source, post.backup_id)
        try:
            await client.edit_message_text(post.destination, post.message_id, text, disable_web_page_preview=True)
        except MessageNotModified:
            pass

    @app.on_message(filters.media_group & filters.caption & mf)
    async def new_multiple(client: Client, message: Message):
        logging.info(f">>>>>> handle_multiple {message.chat.id, message.caption.html}", )

        source = get_source(message.chat.id)

        text = await debloat_text(message, client)
        if not text:
            return

        mg = await client.get_media_group(message.chat.id, message.id)

        backup_id = await backup_multiple(client, mg)
        text = format_text(text, message, source, backup_id)

        if message.reply_to_message_id is not None:
            reply_post = get_post(message.chat.id, message.reply_to_message_id)
            if reply_post is None:
                reply_id = None
            else:
                reply_id = reply_post.message_id
        else:
            reply_id = None

        msgs = await client.copy_media_group(source.destination,
                                             from_chat_id=message.chat.id,
                                             message_id=message.id,
                                             captions=text)

        set_post(Post(
            msgs[0].chat.id,
            msgs[0].id,
            message.chat.id,
            message.id,
            backup_id,
            reply_id,
            text
        ))

    @app.on_message(filters.caption & mf)
    async def new_single(client: Client, message: Message):
        logging.info(f">>>>>> handle_single {message.chat.id}")

        source = get_source(message.chat.id)

        text = await debloat_text(message, client)
        if not text:
            return

        backup_id = await backup_single(client, message)
        logging.info(f">>>>>> handle_single {source, message.chat.id, backup_id}")
        text = format_text(text, message, source, backup_id)

        if message.reply_to_message_id is not None:
            reply_post = get_post(message.chat.id, message.reply_to_message_id)
            if reply_post is None:
                reply_id = None

            else:
                reply_id = reply_post.message_id
        else:
            reply_id = None

        logging.info(f"---- new single {client.name}----- {source}")
        msg = await message.copy(source.destination, caption=text)  # media caption too long

        set_post(Post(
            msg.chat.id,
            msg.id,
            message.chat.id,
            message.id,
            backup_id,
            reply_id,
            text
        ))

        logging.info(f"----------------------------------------------------")

    #   logging.info(f">>>>>>>>>>>>>>>>>>>>> file_id ::::::::::::", message.photo.file_id)
    #  logging.info(f">>>>>>>>>>>>>>>>>>>>> file_unique_id ::::::::::::", message.photo.file_unique_id)

    @app.on_edited_message(filters.caption & mf)
    async def edit_caption(client: Client, message: Message):
        logging.info(f">>>>>> edit_caption {message.chat.id, message.caption.html}", )

        if message.date < (datetime.now() - timedelta(weeks=1)):
            return

        await asyncio.sleep(60)
        post = get_post(message.chat.id, message.id)

        if post is None:
            if message.media_group_id is None:
                await new_single(client, message)
            else:
                await new_multiple(client, message)
            return

        source = get_source(message.chat.id)

        text = await debloat_text(message, client)
        if not text:
            return

        text = format_text(text, message, source, post.backup_id)

        try:
            logging.info(f"edit_caption ::::::::::::::::::::: {post}", )
            await client.edit_message_caption(post.destination, post.message_id, text)
        except MessageNotModified:
            pass

    @app.on_message(filters.command("join"))
    async def handle_join(client: Client, message: Message):
        logging.info(f"join by user {message.from_user.id}")

        try:
            chat = await client.join_chat(message.text.split(" ")[1])

            await message.reply_text(f"Tried to join. Result:\n\n{chat}")
        except Exception as e:
            await message.reply_text(f"Tried to join. Error:\n\n{e}")

    @app.on_message(filters.command("leave"))
    async def handle_join(client: Client, message: Message):
        logging.info(f"leave by user {message.from_user.id}")

        chat = await client.leave_chat(message.text.split(" ")[1])
        await message.reply_text(f"Tried to leave. Result:\n\n{chat}")

    try:
        await app.run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    asyncio.run(main())
