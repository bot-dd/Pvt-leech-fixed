#!/usr/bin/env python3
from aiofiles.os import path as aiopath, makedirs
from aiofiles import open as aiopen
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import PyMongoError
from dotenv import dotenv_values

from bot import DATABASE_URL, user_data, rss_dict, LOGGER, bot_id, config_dict, aria2_options, qbit_options, bot_loop


class DbManger:
    def __init__(self):
        self.__err = False
        self.__db = None
        self.__conn = None
        self.__connect()

    def __connect(self):
        try:
            self.__conn = AsyncIOMotorClient(DATABASE_URL)
            self.__db = self.__conn.wzmlx
        except PyMongoError as e:
            LOGGER.error(f"Error in DB connection: {e}")
            self.__err = True

    async def db_load(self):
        if self.__err:
            return
        await self.__db.settings.config.update_one({'_id': bot_id}, {'$set': config_dict}, upsert=True)
        await self.__db.settings.aria2c.update_one({'_id': bot_id}, {'$set': aria2_options}, upsert=True)
        await self.__db.settings.qbittorrent.update_one({'_id': bot_id}, {'$set': qbit_options}, upsert=True)

        if await self.__db.users[bot_id].find_one():
            rows = self.__db.users[bot_id].find({})
            async for row in rows:
                uid = row['_id']
                del row['_id']
                thumb_path = f'Thumbnails/{uid}.jpg'
                rclone_path = f'wcl/{uid}.conf'
                wm_path = f'wm/{uid}.png'
                try:
                    if row.get('thumb'):
                        await makedirs('Thumbnails', exist_ok=True)
                        async with aiopen(thumb_path, 'wb+') as f:
                            await f.write(row['thumb'])
                        row['thumb'] = thumb_path
                    if row.get('rclone'):
                        await makedirs('rclone', exist_ok=True)
                        async with aiopen(rclone_path, 'wb+') as f:
                            await f.write(row['rclone'])
                        row['rclone'] = rclone_path
                    if row.get('watermark'):
                        await makedirs('wm', exist_ok=True)
                        async with aiopen(wm_path, 'wb+') as f:
                            await f.write(row['watermark'])
                        row['watermark'] = wm_path
                except:
                    continue
                user_data[uid] = row
            LOGGER.info("Users data has been imported from Database")

        if await self.__db.rss[bot_id].find_one():
            rows = self.__db.rss[bot_id].find({})
            async for row in rows:
                user_id = row['_id']
                del row['_id']
                rss_dict[user_id] = row
            LOGGER.info("Rss data has been imported from Database.")

        self.__conn.close

    async def update_config(self, config: dict):
        if self.__err:
            return
        await self.__db.settings.config.update_one({'_id': bot_id}, {'$set': config}, upsert=True)
        self.__conn.close

    async def update_aria2(self, key: str, value: str):
        if self.__err:
            return
        await self.__db.settings.aria2c.update_one({'_id': bot_id}, {'$set': {key: value}}, upsert=True)
        self.__conn.close

    async def update_qbittorrent(self, key: str, value):
        if self.__err:
            return
        await self.__db.settings.qbittorrent.update_one({'_id': bot_id}, {'$set': {key: value}}, upsert=True)
        self.__conn.close

    async def update_private_file(self, file_path: str):
        if self.__err:
            return
        await self.__db.settings.private_files.update_one({'_id': bot_id}, {'$set': {'file_path': file_path}}, upsert=True)
        self.__conn.close

    async def update_deploy_config(self):
        if self.__err:
            return
        current_config = dict(dotenv_values('config.env'))
        await self.__db.settings.deployConfig.replace_one({'_id': bot_id}, current_config, upsert=True)
        self.__conn.close

    async def update_user_data(self, user_id):
        if self.__err:
            return
        data = user_data[user_id]
        for f in ['thumb', 'rclone', 'watermark']:
            if data.get(f):
                del data[f]
        await self.__db.users[bot_id].replace_one({'_id': user_id}, data, upsert=True)
        self.__conn.close

    async def get_incomplete_tasks(self):
        notifier_dict = {}
        if self.__err:
            return notifier_dict
        if await self.__db.tasks[bot_id].find_one():
            rows = self.__db.tasks[bot_id].find({})
            async for row in rows:
                cid = row.get('cid')
                tag = row.get('tag')
                source = row.get('source', 'Unknown Source')  # ✅ KeyError fixed

                if cid in notifier_dict:
                    if tag in notifier_dict[cid]:
                        notifier_dict[cid][tag].append({row['_id']: source})
                    else:
                        notifier_dict[cid][tag] = [{row['_id']: source}]
                else:
                    notifier_dict[cid] = {tag: [{row['_id']: source}]}
        await self.__db.tasks[bot_id].drop()
        self.__conn.close
        return notifier_dict

    async def add_incomplete_task(self, cid, link, tag, msg_link, msg):
        if self.__err:
            return
        await self.__db.tasks[bot_id].insert_one({
            '_id': link,
            'cid': cid,
            'tag': tag,
            'source': msg_link,
            'org_msg': msg
        })
        self.__conn.close

    async def rm_complete_task(self, link):
        if self.__err:
            return
        await self.__db.tasks[bot_id].delete_one({'_id': link})
        self.__conn.close

    async def update_pm_users(self, user_id):
        if self.__err:
            return
        if not await self.__db.pm_users[bot_id].find_one({'_id': user_id}):
            await self.__db.pm_users[bot_id].insert_one({'_id': user_id})
            LOGGER.info(f'New PM User Added : {user_id}')
        self.__conn.close

    async def rss_update_all(self):
        if self.__err:
            return
        for user_id in rss_dict:
            await self.__db.rss[bot_id].replace_one({'_id': user_id}, rss_dict[user_id], upsert=True)
        self.__conn.close

    async def rss_update(self, user_id):
        if self.__err:
            return
        await self.__db.rss[bot_id].replace_one({'_id': user_id}, rss_dict[user_id], upsert=True)
        self.__conn.close

    async def trunc_table(self, name):
        if self.__err:
            return
        await self.__db[name][bot_id].drop()
        self.__conn.close


# Run initial DB load if DATABASE_URL is available
if DATABASE_URL:
    bot_loop.run_until_complete(DbManger().db_load())
