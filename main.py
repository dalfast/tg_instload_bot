import instaloader
from instaloader import Profile, Post, Hashtag, Highlight
import asyncio
import db
from aiogram import Bot, Dispatcher, executor, filters, types
API_TOKEN = ''
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
conn = db.create_connection()
L = instaloader.Instaloader(download_video_thumbnails=False,download_comments=False,save_metadata=False,compress_json=False,max_connection_attempts=5)
try:
   L.load_session_from_file('', filename='')
except:
   L.login('', '')
   L.save_session_to_file('')
# Get instan
highlight = 0
highlights = 0
story = 0
user = 0
profile = 0
userid = 0
key = {'ru':['Привет, отправь мне ссылку или юзернейм профиля, либо пост.','Это приватный профиль.','Неправильная ссылка или юзернейм.',
    'Скачать истории','Нет историй','Скачать актуальное','Нет актуальных','Скачать публикации:','Подписки:','Подписчики:','Актуальное','Перейти','Чтобы скачать историю, отправьте  ссылку на профиль'],
       'en':['Hello, send me your profile link or username or post.','This is a private profile.','Invalid link or username.',
    'Download stories','No stories','Download highlights','No highlights','Download posts:','Followees:','Followers:','Highlights','Link','For download stories send profile link first']}
@dp.message_handler(commands=['start','lang'])
async def start(message: types.Message):
    row = db.execute_one_query(conn, f'SELECT * FROM users WHERE user_id = "{message.from_user.id}"')
    if row == None:
        db.execute_query(conn, F'INSERT INTO users VALUES ("{message.from_user.id}","en")')
    lang = types.InlineKeyboardMarkup(row_width=2).add(
    types.InlineKeyboardButton(text=f'Русский', callback_data="ru"),
    types.InlineKeyboardButton(text=f'English', callback_data='en'))
    await bot.send_message(message.chat.id,'Hello, choose language :)', reply_markup=lang)


@dp.message_handler()
async def menu(message: types.Message):
    global user, userid, profile
    row = db.execute_one_query(conn, f'SELECT * FROM users WHERE user_id = "{message.from_user.id}"')
    msg = message.text
    if '/s/' in msg:
        await message.reply(key[row[1]][12])
    elif 'instagram.com/p/' in msg:
        SHORTCODE = msg.split('/p/')[1].split('/?')[0]
        post = Post.from_shortcode(L.context, SHORTCODE)
        if post.owner_profile.is_private == True:
            await message.reply(key[row[1]][1])
        else:
            await post_downloader(message, post=post)
    elif 'instagram.com/' in msg:
        user = msg.split('.com/')[1][0:-1]
        if '?' in msg: user = msg.split('.com/')[1].split('?')[0]
        profile = Profile.from_username(L.context, user)
        userid = profile.userid
        print(userid)
        if profile.is_private == True:
            await message.reply(key[row[1]][1])
        else:
            await post_downloader(message, posts=1)
    else:
        try:
            msg = msg.replace('@','')
            profile = Profile.from_username(L.context, msg)
            userid = profile.userid
            if profile.is_private == True:
                await message.reply(key[row[1]][1])
            else:
                await post_downloader(message, posts=1)
        except:
            await message.reply(key[row[1]][2])


async def post_downloader(message, post=0, posts=0):
    row = db.execute_one_query(conn, f'SELECT * FROM users WHERE user_id = "{message.from_user.id}"')
    if posts == 0:
        post_info = post_markup(message.from_user.id, post)
        if post.typename == 'GraphImage':
            await types.ChatActions.upload_photo()
            await bot.send_photo(message.chat.id, post.url, caption=post.caption, reply_markup=post_info)
        elif post.typename == 'GraphVideo':
            await types.ChatActions.upload_video()
            await bot.send_video(message.chat.id, post.video_url, caption=post.caption, reply_markup=post_info)
        elif post.typename == 'GraphSidecar':
            media = types.MediaGroup()
            for edge_number, sidecar_node in enumerate(post.get_sidecar_nodes(), start=1):
                if sidecar_node.is_video:
                    await types.ChatActions.upload_video()
                    media.attach_video(sidecar_node.video_url)
                else:
                    await types.ChatActions.upload_photo()
                    media.attach_photo(sidecar_node.display_url)
            msg = await bot.send_media_group(message.chat.id, media)
            await msg[0].reply(post.caption, reply_markup=post_info)
    else:
        if profile.has_public_story: story = key[row[1]][3]
        else: story = key[row[1]][4]
        if profile.has_highlight_reels: high = key[row[1]][5]
        else: high = key[row[1]][6]
        info = types.InlineKeyboardMarkup(row_width=2)
        a = types.InlineKeyboardButton(text=f'{key[row[1]][7]} {profile.mediacount}', callback_data=f"posts-{profile.username}-0")
        b = types.InlineKeyboardButton(text=f'{key[row[1]][8]} {profile.followees}', callback_data='x')
        c = types.InlineKeyboardButton(text=f'{key[row[1]][9]} {profile.followers}', callback_data="x")
        d = types.InlineKeyboardButton(text=story, callback_data=f"stories-{profile.userid}-0")
        e = types.InlineKeyboardButton(text=high, callback_data=f"highlights-{profile.userid}-0")
        info.add(b, c, e, d, a)
        await bot.send_photo(message.chat.id, profile.profile_pic_url,caption=f'instagram.com/{profile.username}/\nBio:\n{profile.biography}', reply_markup=info)

@dp.callback_query_handler()
async def inline_kb_answer_callback_handler(query: types.CallbackQuery):
    answer_data = query.data
    global highlight
    global userid
    global user
    id = query.from_user.id
    text = query.message.caption
    if answer_data == 'ru' or answer_data == 'en':
        db.execute_query(conn, f'UPDATE users SET lang = "{answer_data}" WHERE user_id = "{id}"')
        await bot.edit_message_text(chat_id=id, message_id=query.message.message_id, text=key[answer_data][0])
    elif len(answer_data) > 1:
        loop, pool, it = map(str, answer_data.split('-'))
        if loop == 'posts':
            user = pool
            await send_posts(id, posts=Profile.from_username(L.context, user).get_posts())
        else:
            userid = int(pool)
            if loop == 'stories':
                await send_stories(id)
            elif loop == 'highlights':
                await info_highlights(id)
            elif loop == 'highlight':
                i = 0
                for highlight in L.get_highlights(userid):
                    if i == int(it):
                        highlight=highlight
                        await send_highlights(id)
                        break
                    i += 1

async def info_highlights(id):
    row = db.execute_one_query(conn, f'SELECT * FROM users WHERE user_id = "{id}"')
    text = key[row[1]][10]
    hl_info = types.InlineKeyboardMarkup(row_width=3)
    i = 1
    for highlight in L.get_highlights(userid):
        hl_info.add(types.InlineKeyboardButton(text=f'{highlight.title[:15]} ({highlight.itemcount})\n', callback_data=f"highlight-{userid}-{i}"))
        i += 1
    await bot.send_message(id,text,reply_markup=hl_info)

async def send_highlights(id):
    for item in highlight.get_items():
        if item.typename == 'GraphStoryImage':
            await types.ChatActions.upload_photo()
            await bot.send_photo(id, item.url,caption=item.date)
        elif item.typename == 'GraphStoryVideo':
            await types.ChatActions.upload_video()
            await bot.send_video(id, item.video_url,caption=item.date)

async def send_stories(id):
    for story in L.get_stories(userids=[userid]):
        for item in story.get_items():
            if item.typename == 'GraphStoryImage':
                await types.ChatActions.upload_photo()
                await bot.send_photo(id, item.url,caption=item.date)
            elif item.typename == 'GraphStoryVideo':
                await types.ChatActions.upload_video()
                await bot.send_video(id, item.video_url,caption=item.date)

def post_markup(id, post):
    row = db.execute_one_query(conn, f'SELECT * FROM users WHERE user_id = "{id}"')
    post_info = types.InlineKeyboardMarkup(row_width=3)
    post_info.add(types.InlineKeyboardButton(text=f'{post.likes}❤', callback_data=f"p"),
    types.InlineKeyboardButton(text=f'{post.comments}💬', callback_data=f"p"),
    types.InlineKeyboardButton(text=key[row[1]][11], url=f"instagram.com/p/{post.shortcode}/"))
    return post_info

async def send_posts(id, posts):
    for post in posts:
        post_info = post_markup(id, post)
        if post.typename == 'GraphImage':
            await types.ChatActions.upload_photo()
            await bot.send_photo(id, post.url,caption=post.caption, reply_markup=post_info)
        elif post.typename == 'GraphVideo':
            await types.ChatActions.upload_video()
            await bot.send_video(id, post.video_url,caption=post.caption, reply_markup=post_info)
        elif post.typename == 'GraphSidecar':
            media = types.MediaGroup()
            for edge_number, sidecar_node in enumerate(post.get_sidecar_nodes(), start=1):
                if sidecar_node.is_video:
                    await types.ChatActions.upload_video()
                    media.attach_video(sidecar_node.video_url)
                else:
                    await types.ChatActions.upload_photo()
                    media.attach_photo(sidecar_node.display_url)
            msg = await bot.send_media_group(id, media)
            if post.caption == None: post.caption = '...'
            await msg[0].reply(post.caption, reply_markup=post_info)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)