#!/usr/bin/env python3
"""
screwie.py - Telegram message printer.

A Telegram bot that listens for messages and prints them
to a connected printer using an external program.

This script requires a valid Telegram bot token,
which must be provided in the config file.

Note:
    Ensure you have permission to act on messages
    and comply with Telegram's terms of service.
"""

import argparse
import configparser
import logging
import os
import subprocess
import tempfile
import zoneinfo

import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont
import telegram
import telegram.ext


CONFIG_FILE = 'screwie.ini'
CONFIG_SECTION = 'screwie'

parser = argparse.ArgumentParser(description='Telegram message printer.')
parser.add_argument(
    '--log-level', '-l',
    choices=('NOTSET', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'),
    default='WARNING',
    help='Logging level'
)
args = parser.parse_args()

logging.basicConfig(level=args.log_level)

config = configparser.ConfigParser()
config_paths = (
    os.path.join('etc', CONFIG_FILE),
    os.path.join(os.path.expanduser('~'), '.config', CONFIG_FILE),
    os.path.join(os.path.dirname(__file__), CONFIG_FILE),
)
files_read = config.read(config_paths)
logging.info(f'Read configuration files: {files_read}')

log_level = config[CONFIG_SECTION].get('log_level')
if log_level:
    logging.getLogger().setLevel(log_level)
    logging.info(f'Logging level set to {log_level} from config file.')

allowed_users = [
    int(id) for id in config[CONFIG_SECTION].get(
        option='allowed_users',
        fallback=''
    ).split()
]
logging.info(f'Allowed users: {allowed_users}')

def handle_start(
        update: telegram.Update,
        context: telegram.ext.CallbackContext
) -> None:
    logging.info(f'User {update.effective_user}: /start')
    if update.effective_user.id in allowed_users:  # type: ignore
        update.message.reply_text('Welcome!')
    else:
        logging.warning(f'Denied: {update.effective_user}')
        update.message.reply_text('Sorry, this bot is private.')

def handle_message(
        update: telegram.Update,
        context: telegram.ext.CallbackContext
) -> None:
    logging.info(f'User {update.effective_user}: message')
    if update.effective_user.id in allowed_users:  # type: ignore
        if update.message.text:
            logging.info(
                f'Processing message from {update.effective_user.username}'  # type: ignore
            )
            width = 384
            font = PIL.ImageFont.truetype(
                font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                size=24
            )
            padding = 8
            spacing = 8

            dummy_img = PIL.Image.new(mode='1', size=(width, 1))
            draw = PIL.ImageDraw.Draw(dummy_img)

            local_tz = zoneinfo.ZoneInfo(config[CONFIG_SECTION].get(
                option='timezone',
                fallback='UTC'
            ))
            text = (
                update.message.date.astimezone(
                    zoneinfo.ZoneInfo(config[CONFIG_SECTION].get(
                        option='timezone',
                        fallback='UTC'
                    ))
                ).isoformat() + '\n' +
                update.effective_user.username +  '\n\n' +  # type: ignore
                update.message.text
            )

            lines = []
            for line in text.splitlines():
                words = line.split()
                current_line = ''
                for word in words:
                    test_line = (current_line + ' ' + word).strip()
                    length = draw.textlength(text=test_line, font=font)
                    if length <= width - 2 * padding:
                        current_line = test_line
                    else:
                        lines.append(current_line)
                        current_line = word
                lines.append(current_line)

            line_height = (
                font.getbbox('A')[3] - font.getbbox('A')[1]
            )
            height = (line_height + spacing) * len(lines) + 2 * padding

            img = PIL.Image.new(
                mode='1',
                size=(width, height),
                color='white'
            )
            draw = PIL.ImageDraw.Draw(img)

            y = padding
            for line in lines:
                draw.text(
                    xy=(padding, y),
                    text=line,
                    fill='black',
                    font=font
                )
                y += line_height + spacing

            with tempfile.NamedTemporaryFile(
                suffix='.png',
                delete=config[CONFIG_SECTION].getboolean(
                    option='delete_temp_files',
                    fallback=True
                )
            ) as tmp:
                img.save(fp=tmp.name, format='PNG')
                logging.info(f'Image saved to temporary file: {tmp.name}')

                try:
                    cmd = (
                        config[CONFIG_SECTION]['printer_script'].split() +
                        [tmp.name]
                    )
                    logging.info(f'Calling external program: {cmd}')
                    subprocess.Popen(cmd)
                except Exception as e:
                    logging.error(f'Failed to call external program: {e}')
    else:
        logging.warning(f'Denied: {update.effective_user}')



    # # Prepare images
    # images = []
    # if update.message.photo:
    #     logging.info("Message contains photo(s)")
    #     # Get highest resolution photo
    #     photo = update.message.photo[-1]
    #     file = context.bot.get_file(photo.file_id)
    #     logging.debug("Downloading photo from: %s", file.file_path)
    #     img_bytes = requests.get(file.file_path).content
    #     images.append(Image.open(BytesIO(img_bytes)))
    #     logging.info("Photo downloaded and loaded")


    # # Paste images below text
    # y_offset = 40
    # for img in images:
    #     img.thumbnail((width - 20, height - y_offset - 10))
    #     canvas.paste(img, (10, y_offset))
    #     y_offset += img.height + 10
    #     logging.debug("Image pasted at y_offset: %d", y_offset)

    # # Save to temp file
    # with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
    #     canvas.save(tmp.name, "PNG")
    #     tmp_path = tmp.name
    #     logging.info("Canvas saved to temporary file: %s", tmp_path)

    # # Call external program with predefined arguments
    # try:
    #     cmd = [EXTERNAL_PROGRAM] + EXTERNAL_ARGS + [tmp_path]
    #     logging.info("Calling external program: %s", ' '.join(cmd))
    #     subprocess.Popen(cmd)
    # except Exception as e:
    #     logging.error("Failed to call external program: %s", e)

    # # Optionally, clean up temp file later


if __name__ == '__main__':
    logging.info('Starting Telegram bot.')
    updater = telegram.ext.Updater(
        token=config[CONFIG_SECTION]['bot_token']
    )
    dispatcher = updater.dispatcher
    dispatcher.add_handler(  # type: ignore
        telegram.ext.CommandHandler(
            command='start',
            callback=handle_start
        )
    )
    dispatcher.add_handler(  # type: ignore
        telegram.ext.MessageHandler(
            filters=telegram.ext.Filters.all,
            callback=handle_message
        )
    )
    updater.start_polling()
    logging.info('Telegram bot started and polling for messages.')
    updater.idle()
