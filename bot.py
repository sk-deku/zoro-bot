import logging
import logging.config

# Get logging configurations
logging.config.fileConfig('logging.conf')
logging.getLogger().setLevel(logging.INFO)
logging.getLogger("pyrogram").setLevel(logging.ERROR)
logging.getLogger("imdbpy").setLevel(logging.ERROR)

from pyrogram import Client, __version__
from pyrogram.raw.all import layer
from database.ia_filterdb import Media, Media2, choose_mediaDB, db as clientDB
from database.users_chats_db import db
from info import SESSION, API_ID, API_HASH, BOT_TOKEN, LOG_STR, LOG_CHANNEL, SECONDDB_URI
from utils import temp
from typing import Union, Optional, AsyncGenerator
from pyrogram import types
from Script import script 
from datetime import date, datetime 
import pytz
from sample_info import tempDict

class Bot(Client):

    def __init__(self):
        super().__init__(
            name=SESSION,
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            workers=200,
            plugins={"root": "plugins"},
            sleep_threshold=10,
        )

    async def start(self):
        b_users, b_chats = await db.get_banned()
        temp.BANNED_USERS = b_users
        temp.BANNED_CHATS = b_chats
        await super().start()
        await Media.ensure_indexes()
        await Media2.ensure_indexes()
        #choose the right db by checking the free space
        stats = await clientDB.command('dbStats')
        #calculating the free db space from bytes to MB
        free_dbSize = round(512-((stats['dataSize']/(1024*1024))+(stats['indexSize']/(1024*1024))), 2)
        if SECONDDB_URI and free_dbSize<10: #if the primary db have less than 10MB left, use second DB.
            tempDict["indexDB"] = SECONDDB_URI
            logging.info(f"Since Primary DB have only {free_dbSize} MB left, Secondary DB will be used to store datas.")
        elif SECONDDB_URI is None:
            logging.error("Missing second DB URI !\n\nAdd SECONDDB_URI now !\n\nExiting...")
            exit()
        else:
            logging.info(f"Since primary DB have enough space ({free_dbSize}MB) left, It will be used for storing datas.")
        await choose_mediaDB()
        me = await self.get_me()
        temp.ME = me.id
        temp.U_NAME = me.username
        temp.B_NAME = me.first_name
        self.username = '@' + me.username
        logging.info(f"{me.first_name} with for Pyrogram v{__version__} (Layer {layer}) started on {me.username}.")
        logging.info(LOG_STR)
        logging.info(script.LOGO)
        tz = pytz.timezone('Asia/Kolkata')
        today = date.today()
        now = datetime.now(tz)
        time = now.strftime("%H:%M:%S %p")
        await self.send_message(chat_id=LOG_CHANNEL, text=script.RESTART_TXT.format(today, time))

    async def stop(self, *args):
        await super().stop()
        logging.info("Bot stopped. Bye.")

    async def iter_messages(
        self,
        chat_id: Union[int, str],
        limit: int,
        offset: int = 0,
    ) -> Optional[AsyncGenerator["types.Message", None]]:
        """Iterate through a chat sequentially.
        This convenience method does the same as repeatedly calling :meth:`~pyrogram.Client.get_messages` in a loop, thus saving
        you from the hassle of setting up boilerplate code. It is useful for getting the whole chat messages with a
        single call.
        Parameters:
            chat_id (``int`` | ``str``):
                Unique identifier (int) or username (str) of the target chat.
                For your personal cloud (Saved Messages) you can simply use "me" or "self".
                For a contact that exists in your Telegram address book you can use his phone number (str).
                
            limit (``int``):
                Identifier of the last message to be returned.
                
            offset (``int``, *optional*):
                Identifier of the first message to be returned.
                Defaults to 0.
        Returns:
            ``Generator``: A generator yielding :obj:`~pyrogram.types.Message` objects.
        Example:
            .. code-block:: python
                for message in app.iter_messages("pyrogram", 1, 15000):
                    print(message.text)
        """
        current = offset
        while True:
            new_diff = min(200, limit - current)
            if new_diff <= 0:
                return
            messages = await self.get_messages(chat_id, list(range(current, current+new_diff+1)))
            for message in messages:
                yield message
                current += 1


app = Bot()
app.run()


async def send_file(user_id, file_id, chat_id):
    """Checks if the user has tokens before sending the file."""
    has_token = await deduct_token(user_id)
    
    if has_token:
        await bot.send_document(chat_id, file_id)
        return "File sent successfully!"
    else:
        verification_link = f"https://public.earn/verify?user={user_id}"
        return f"⚠️ You have 0 tokens left! Please verify here to get 15 more tokens: {verification_link}"


@Client.on_message(filters.command("verify") & filters.private)
async def verify_user(client, message):
    """Verifies a user and grants tokens if they completed the shortlink verification."""
    user_id = message.from_user.id

    # Simulating verification check (In real-world, integrate API check)
    verified = True  # Replace this with actual verification logic

    if verified:
        await add_user_token(user_id, 15)
        await message.reply("✅ Verification successful! You received 15 tokens.")
    else:
        await message.reply("❌ Verification failed. Please complete the shortlink verification.")

@Client.on_message(filters.command("addtokens") & filters.user(ADMIN_ID))
async def add_tokens_admin(client, message):
    """Allows admin to add tokens to a user manually."""
    args = message.text.split()
    if len(args) < 3:
        await message.reply("Usage: /addtokens @username 10")
        return

    username = args[1].replace("@", "")
    tokens = int(args[2])

    user_data = await users_collection.find_one({"username": username})
    if user_data:
        await admin_add_tokens(user_data["user_id"], tokens)
        await message.reply(f"✅ Added {tokens} tokens to {username}.")
    else:
        await message.reply("❌ User not found in the database.")


@Client.on_message(filters.command("addtokens") & filters.user(ADMIN_ID))
async def add_tokens_admin(client, message):
    """Allows admin to add tokens to a user using their user ID."""
    args = message.text.split()
    if len(args) < 3:
        await message.reply("Usage: /addtokens user_id 10")
        return

    try:
        user_id = int(args[1])
        tokens = int(args[2])
        
        success = await admin_add_tokens(user_id, tokens)
        if success:
            await message.reply(f"✅ Added {tokens} tokens to user {user_id}.")
        else:
            await message.reply("❌ User not found in the database.")
    except ValueError:
        await message.reply("❌ Invalid user ID or token amount.")
