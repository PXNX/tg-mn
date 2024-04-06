import asyncio
import logging
import os
import re
from datetime import datetime
from typing import Final

from pyrogram import Client, filters, idle
from pyrogram.enums import ParseMode
from pyrogram.types import Message, InputMedia, InputMediaVideo, InputMediaPhoto, InputMediaAnimation

import config
from data.db import set_post, get_slave_post_ids, get_post, update_post_media
from data.lang import MASTER, SLAVES, SLAVE_DICT
from data.model import Post, get_filetype
from translation import format_text, translate
from utils import get_file_id, get_input_media



LOG_FILENAME: Final[str] = rf"./logs/{datetime.now().strftime('%Y-%m-%d/%H-%M-%S')}.log"
os.makedirs(os.path.dirname(LOG_FILENAME), exist_ok=True)
logging.basicConfig(
    format="%(asctime)s %(levelname)-5s %(funcName)-20s [%(filename)s:%(lineno)d]: %(message)s",
    encoding="utf-8",
    filename=LOG_FILENAME,
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S'
)


async def main():
    app = Client(
        name="Premium",
        api_id=config.API,
        api_hash=config.HASH,
        phone_number=config.NUMBER,
        parse_mode=ParseMode.HTML
    )

    bf = filters.channel & filters.chat(MASTER.channel_id) & filters.incoming
    mf = bf & (filters.photo | filters.video | filters.animation)

    logging.info("-- STARTED // TG-MN  --")

    @app.on_message(

        filters.text & filters.regex(rf"^#{MASTER.breaking}", re.IGNORECASE))  #bf &
    async def handle_breaking(client: Client, message: Message):
        print("handle_breaking")
        await message.delete()

        # todo: what about supporting Breaking with images/videos supplied?
        # todo: replace LI with actual lang keys

        master_caption = f"🚨 #{MASTER.breaking}\n\n{format_text(message.text.html)}"
        master_post = await client.send_photo(chat_id=message.chat.id, photo=f"./res/{MASTER.lang_key}/breaking.png",
                                              caption=master_caption)
        set_post(Post(master_post.id, "li", master_post.id, file_type=get_filetype(master_post.media),
                      file_id=master_post.photo.file_id))

        for lang in SLAVES:
            translated_caption = f"🚨 #{lang.breaking}\n\n{format_text(translate(message.text.html, lang), lang)}"
            slave_post = await client.send_photo(chat_id=message.chat.id, photo=f"./res/{lang.lang_key}/breaking.png",
                                                 caption=translated_caption)
            set_post(Post(master_post.id, "li", slave_post.id, file_type=get_filetype(slave_post.media),
                          file_id=slave_post.photo.file_id))

    @app.on_edited_message(filters.caption & filters.incoming)
    # fixme: does incoming work for edited??
    # filters.caption & filters.incoming    # bf &
    async def handle_edit(client: Client, message: Message):
        print("handle_edit")
        caption_changed = len(message.caption.html .find(MASTER.footer)) != 0
        if caption_changed:
            await message.edit_caption(format_text(message.caption.html))
            print("editing MASTER")

        for lang_key, slave_post_id in get_slave_post_ids(message.id).items():
            lang = SLAVE_DICT[lang_key]
            translated_caption = format_text(translate(message.caption.html, lang), lang)
            old_slave_post = get_post(lang.channel_id, slave_post_id)
            new_file_id = get_file_id(message)

            # still need to figure out how to remove needless translations here, if caption remained same, but media is different now

            if new_file_id == old_slave_post.file_id:
                return await client.edit_message_caption(chat_id=lang.channel_id, message_id=slave_post_id,
                                                         caption=translated_caption)

            slave_post = await client.edit_message_media(chat_id=lang.channel_id, message_id=slave_post_id,
                                                         media=get_input_media(message, translated_caption))

            update_post_media(lang_key, slave_post_id, get_filetype(slave_post.media), get_file_id(slave_post))
            print(slave_post)

    @app.on_message(bf & filters.media & filters.caption & ~filters.media_group & filters.incoming)  # bf &
    async def handle_single(client: Client, message: Message):
        print("handle_single")
        for slave in SLAVES:
            final_caption = format_text(translate(message.caption.html, slave), slave)

            msg = await message.copy(chat_id=message.chat.id, caption=final_caption)

            # set_post(Post())

        await message.edit_caption(format_text(message.caption.html, MASTER))

    try:
        print("RUN")
        await app.start()
        await idle()

    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    asyncio.run(main())
