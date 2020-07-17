import discord
import asyncio
import sqlite3
import json
import requests
import traceback
from conf.commands import Commands
from conf.config import Config
from conf.constants import Constants
from datetime import datetime

# Dictionary factory for sqlite.
def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

client = discord.Client()
conn = sqlite3.connect('noticeboard.db')
conn.row_factory = dict_factory

# Update 
async def update_board():
    while True:
        available = await isNoticeMessageAvailable()
        embedMode = getSetting(Constants.SETTING_EMBED)
        if available:
            # If we have an existing message.
            noticeMessage = await getNoticeMessage()

            # Check if the message's contents are different, and edit if so.
            if embedMode == "0":
                editedMessage = getNoticeboard()
                if editedMessage != noticeMessage.content:
                    await noticeMessage.edit(content=str(getNoticeboard()), embed=None)
            else:
                embedded = getEmbed()
                await noticeMessage.edit(content="", embed=embedded)
        else:
            # We should send a new one.
            channel = client.get_channel(int(getSetting(Constants.SETTING_CHANNEL)))
            if embedMode == "0":
                noticeMessage = await channel.send(content=getNoticeboard(), embed=None)
            else:
                noticeMessage = await channel.send(content="", embed=getEmbed())
            updateSetting(Constants.SETTING_MESSAGE, noticeMessage.id)
        await asyncio.sleep(30)

@client.event
async def on_ready():
    print('Logged in as: ' + client.user.name)
    client.loop.create_task(update_board())

@client.event
async def on_message(message):
    # Filter own messages.
    if message.author.id == Config.BOT_ID:
        return
    # Check the message matches the listening channel.
    if str(message.channel.id) != getSetting(Constants.SETTING_CHANNEL):
        if type(message.channel) == discord.channel.DMChannel:
            print(str(message.channel) + ' - ' + str(message.author) + ': ' + str(message.content))
        return
    print(str(message.channel) + ' - ' + str(message.author) + ': ' + str(message.content))
    # Check that message starts with the prefix.
    if message.content[0] != getSetting(Constants.SETTING_PREFIX):
        return
    command = message.content[1:].split(" ")
    # Help
    if command[0] == Commands.HELP:
        await sendMessage(message.author, helpText())
    # Set boss.
    if command[0] == Commands.SETBOSS:
        success = setBoss(command)
        await react(message, success)
    # Add recommended.
    if command[0] == Commands.ADDRECOMMENDED:
        success = addOrUpdateStreamer(command[1], Constants.RECOMMENDED)
        await react(message, success)
    # Add community.
    if command[0] == Commands.ADDCOMMUNITY:
        success = addOrUpdateStreamer(command[1], Constants.COMMUNITY)
        await react(message, success)
    # Remove streamer.
    if command[0] == Commands.REMOVE:
        success = removeStreamer(command[1])
        await react(message, success)
    # List streamers.
    if command[0] == Commands.LIST:
        await message.channel.send(printStreamerList())
    # Embed mode.
    if command[0] == Commands.EMBED:
        success = updateSetting(Constants.SETTING_EMBED, command[1])
        await react(message, success)

def getOfflineEmbed(embedded, bossImage):
    recommended = getLiveRecommended()
    community = getLiveCommunity()

    embedded.add_field(name="LIVE RECOMMENDED STREAMS", value="-----", inline=False)

    for rec in recommended:
        embedded.add_field(name=rec['display'], value="[Playing "+rec['game']+"]("+rec['url']+")", inline=True)
    if len(recommended) < 1:
        embedded.add_field(name="No recommended streams are live at the moment!", value="\u200B", inline=False)
    embedded.add_field(name="--------------------------", value="\u200B", inline=False)
    embedded.add_field(name="LIVE COMMUNITY STREAMS", value="-----", inline=False)

    for com in community:
        embedded.add_field(name=com['display'], value="[Playing "+com['game']+"]("+com['url']+")", inline=True)
    if len(community) < 1:
        embedded.add_field(name="No community channels are live at the moment!", value="\u200B", inline=False)
    
    if bossImage != "":
        embedded.set_thumbnail(url=bossImage)

    embedded.set_footer(text=datetime.now().strftime("%m/%d/%y - %H:%M:%S"))    
    return embedded

# Gets the content for the embed.
def getEmbed():
    
    boss = getBoss()
    # Boss not set.
    if boss is None:
        embedded = discord.Embed(title="Stream Noticeboard", description="No boss set, set one now with " + getSetting(Constants.SETTING_PREFIX) + Commands.SETBOSS + r" {user}", color=0x00FFFF)
        embedded = getOfflineEmbed(embedded, "")
        return embedded

    embedded = discord.Embed(title="Stream Noticeboard", description="", color=0xFF0000)
    liveBossInfo = getBossInfo()
    if len(liveBossInfo) > 0:
        # The streamboss is live.
        streamboss = liveBossInfo[0]
        embedded.add_field(name=Constants.RECORD_EMOJI + str(" " + streamboss['display'] + " is live!"), value="Join now: "+streamboss['url'], inline=False)
        embedded.add_field(name=streamboss['title']+ "\u200B", value=streamboss['game'] + "\u200B", inline=False)
        embedded.set_image(url=streamboss['img'])

        embedded.set_footer(text=datetime.now().strftime("%m/%d/%y - %H:%M:%S"))   
    else:
        # The streamboss is not live.
        embedded = getOfflineEmbed(embedded, getLogo(boss[Constants.DB_STREAM_BROADCASTID]))
    return embedded

# Removes a streamer from the list.
def removeStreamer(user):
    try:
        c = conn.cursor()
        c.execute('''DELETE FROM "main"."streamers" WHERE "username" = ?''', (user.lower(),))
        count = c.rowcount
        conn.commit()
        return (count > 0)
    except:
        traceback.print_exc()
        return False

# Adds a user to the streamer list.
def addOrUpdateStreamer(user, level):
    try:
        broadcasterId = getBroadcastId(user)
        doTheyExist = checkIfStreamerExists(broadcasterId)
        if doTheyExist:
            updateStreamer(user, broadcasterId, level)
        else:
            addStreamer(user, broadcasterId, level)
        return True
    except:
        traceback.print_exc()
        return False

# Sets the boss of the stream. Command[1] is the user.
def setBoss(command):
    try:
        broadcasterId = getBroadcastId(command[1])
        doTheyExist = checkIfStreamerExists(broadcasterId)
        removeBoss()
        if doTheyExist:
            updateStreamer(command[1], broadcasterId, Constants.STREAM_BOSS)
        else:
            addStreamer(command[1], broadcasterId, Constants.STREAM_BOSS)
        return True
    except:
        traceback.print_exc()
        return False

# Gets the current boss.
def getBoss():
    try:
        c = conn.cursor()
        c.execute('''SELECT * FROM "streamers" WHERE "type" = ?''', (Constants.STREAM_BOSS,))
        return c.fetchone()
    except:
        traceback.print_exc()
        return None

# Gets a streamer.
def getStreamer(username):
    try:
        broadcasterId = getBroadcastId(username)
        doTheyExist = checkIfStreamerExists(broadcasterId)
        if doTheyExist:
            c = conn.cursor()
            c.execute('SELECT * FROM "streamers" WHERE username = ?', (username.lower(),))
            return c.fetchone()
        else:
            return None
    except:
        traceback.print_exc()
        return None

# Updates an existing streamer 
def updateStreamer(user, broadcasterId, broadcasterType):
    c = conn.cursor()
    c.execute('''UPDATE "streamers" SET "type" = ?, "display_name" = ?, "username" = ?
     WHERE "broadcast_id" = ?''', (broadcasterType, user, user.lower(), broadcasterId))
    conn.commit()
    return True

# Adds a streamer to the database with the given parameters.
def addStreamer(user, broadcasterId, broadcasterType):
    c = conn.cursor()
    c.execute('''INSERT INTO "main"."streamers"("username","type","broadcast_id","display_name") 
    VALUES (?,?,?,?)''', (user.lower(), broadcasterType, broadcasterId, user))
    conn.commit()
    return True

# Contact Twitch API for user's broadcaster ID.
def getBroadcastId(username):
    headers = {'Accept': 'application/vnd.twitchtv.v5+json', 'Client-ID': Config.CLIENT_ID}
    response = requests.get('https://api.twitch.tv/kraken/users?login=' + username, headers=headers)
    responseJson = response.json()
    return responseJson['users'][0]['_id']

# Makes previous stream boss a suggested.
def removeBoss():
    c = conn.cursor()
    c.execute('''UPDATE "streamers" SET "type" = ? WHERE "type" = ?''', (Constants.RECOMMENDED, Constants.STREAM_BOSS))
    conn.commit()

# Checks if the streamer exists in the database. Returns True / False
def checkIfStreamerExists(broadcasterId):
    c = conn.cursor()
    c.execute('SELECT EXISTS(SELECT 1 FROM "streamers" WHERE broadcast_id=?)', (broadcasterId,))
    exists = c.fetchone()['EXISTS(SELECT 1 FROM "streamers" WHERE broadcast_id=?)']
    return (exists == 1)

# Grab setting from the database.
def getSetting(setting):
    c = conn.cursor()
    c.execute('SELECT "value" FROM "settings" WHERE "name" = ?', (setting,))
    return c.fetchone()["value"]

# Update setting in database.
def updateSetting(setting, value):
    try:
        c = conn.cursor()
        c.execute('UPDATE "settings" SET "value" = ? WHERE "name" = ?', (value, setting))
        conn.commit()
        return True
    except:
        traceback.print_exc()
        return False

# Send a message to the discord channel supplied.
async def sendMessage(channel, content):
    return await channel.send(content)

# React with thumbs up or down depending on boolean.
async def react(message, goodBad):
    if goodBad:
        await message.add_reaction(Constants.GOOD_EMOJI)
    else:
        await message.add_reaction(Constants.BAD_EMOJI)

# Check if messageID is available.
async def isNoticeMessageAvailable():
    try:
        channel = client.get_channel(int(getSetting(Constants.SETTING_CHANNEL)))
        message = await channel.fetch_message(int(getSetting(Constants.SETTING_MESSAGE)))
        if message.author.id == Config.BOT_ID:
            return True
    except discord.NotFound:
        print("Message not found.")
    except:
        traceback.print_exc()
    return False

# Retrieve the noticeboard message.
async def getNoticeMessage():
    try:
        channel = client.get_channel(int(getSetting(Constants.SETTING_CHANNEL)))
        message = await channel.fetch_message(int(getSetting(Constants.SETTING_MESSAGE)))
        return message
    except discord.NotFound:
        print("Message not found.")
    except:
        traceback.print_exc()

# Get the noticeboard contents.
def getNoticeboard():
    contents = ""
    boss = getBoss()
    # Boss not set.
    if boss is None:
        contents += "No boss set, set one now with " + getSetting(Constants.SETTING_PREFIX) + Commands.SETBOSS + r" {user}" + "\n\n"
        contents += getOfflineMessage()
        return contents

    if isUserLive(boss[Constants.DB_STREAM_BROADCASTID]):
        # The streamboss is live.
        contents += getStreamBossMessage(boss)
    else:
        # The streamboss is not live.
        contents += ".\nWhile **" + boss[Constants.DB_STREAM_DISPLAY] + "** is OFFLINE, check out who else is streaming:\n\n"
        contents += getOfflineMessage()
    return contents

# Print out the message saying the Streamboss is live.
# TODO: Make prettier?
def getStreamBossMessage(boss):
    return str(boss[Constants.DB_STREAM_DISPLAY]) + " is live! "+Constants.RECORD_EMOJI+" Join now: "+twitchLink(boss[Constants.DB_STREAM_USER])

# Print out the message for when Streamboss is offline.
# TODO: Make prettier? Only ping TwitchAPI once!
def getOfflineMessage():
    msg = ""
    recommended = getLiveRecommended()
    community = getLiveCommunity()
    msg += "**Live Recommended Streams** "+Constants.GOOD_EMOJI+"\n"

    for rec in recommended:
        msg += "**" + rec['display'] + ":** "+ rec['game']+ "\n" + rec['url'] + "\n\n"
    if len(recommended) < 1:
        msg += "NO RECOMMENDED CHANNELS ARE LIVE AT THE MOMENT!\n\n"
    
    msg += "--------------------\n"
    msg += "**Live Community Streams** "+Constants.NONBINARY_PEOPLE+"\n"
    for com in community:
        msg += "**" + com['display'] + ":** "+ com['game'] + "\n" + com['url'] + "\n\n"
    if len(community) < 1:
        msg += "NO COMMUNITY CHANNELS ARE LIVE AT THE MOMENT!\n\n"

    return msg

# Prints out the streamers.
def printStreamerList():
    boss = getStreamerList(Constants.STREAM_BOSS)
    recommended = getStreamerList(Constants.RECOMMENDED)
    community = getStreamerList(Constants.COMMUNITY)
    contents = ".\n\n**STREAMER LIST**\n\n"

    contents += "**Stream Boss**\n" + boss[0][Constants.DB_STREAM_DISPLAY]

    contents += "\n\n"
    contents += "**Recommended Channels**\n"
    for rec in recommended:
        contents += rec[Constants.DB_STREAM_DISPLAY] + "\n"
    
    contents += "\n"
    contents += "**Community Channels**\n"
    for com in community:
        contents += com[Constants.DB_STREAM_DISPLAY] + "\n"
    
    return contents

# Gets a list of all of the streamers.
def getStreamerList(type):
    c = conn.cursor()
    c.execute('SELECT * FROM "streamers" WHERE "type" = ?', (type,))
    return c.fetchall()

# Returns true if the userId provided is live, false if not.
def isUserLive(broadcastId):
    headers = {'Accept': 'application/vnd.twitchtv.v5+json', 'Client-ID': 'nwoafaczjhgkhqntjv34utror7agjk'}
    response = requests.get('https://api.twitch.tv/kraken/streams/' + broadcastId, headers=headers)
    responseJson = response.json()
    if responseJson['stream'] is None:
        return False
    else:
        return True

# Gets info about live recommended users.
def getLiveRecommended():
    recommended = getStreamerList(Constants.RECOMMENDED)
    return getLiveList(recommended)

# Gets info about live community users.
def getLiveCommunity():
    community = getStreamerList(Constants.COMMUNITY)
    return getLiveList(community)

# Gets info about boss.
def getBossInfo():
    boss = getStreamerList(Constants.STREAM_BOSS)
    return getLiveList(boss)

# Get info on users live in supplied list.
def getLiveList(ulist):
    users = ""
    for u in ulist:
        users += u[Constants.DB_STREAM_BROADCASTID] + ","

    headers = {'Accept': 'application/vnd.twitchtv.v5+json', 'Client-ID': 'nwoafaczjhgkhqntjv34utror7agjk'}
    response = requests.get('https://api.twitch.tv/kraken/streams/?limit=100&channel=' + users, headers=headers)
    responseJson = response.json()
    liveList = []
    for stream in responseJson['streams']:
        liveUser = dict(display=stream['channel']['display_name'], game=stream['game'], title=stream['channel']['status'], url=stream['channel']['url'], img=stream['channel']['logo'])
        liveList.append(liveUser)
    return liveList

# Get broadcast ID logo
def getLogo(userid):
    headers = {'Accept': 'application/vnd.twitchtv.v5+json', 'Client-ID': 'nwoafaczjhgkhqntjv34utror7agjk'}
    response = requests.get('https://api.twitch.tv/kraken/users/' + userid, headers=headers)
    responseJson = response.json()
    return responseJson['logo']

def twitchLink(username):
    return "https://twitch.tv/"+username

# Get help list.
def helpText():
    p = getSetting(Constants.SETTING_PREFIX)
    msg = "Helplist\n\n"
    msg += p + Commands.LIST + ": Retrieves a full formatted list of registered streamers.\n"
    msg += p + Commands.SETBOSS + r" {proper caps username}" + ": Sets a user to the boss of the stream. They will dominate the noticeboard when live.\n"
    msg += p + Commands.ADDRECOMMENDED + r" {proper caps username}" + ": Sets a user to the recommended list of streamers.\n"
    msg += p + Commands.ADDCOMMUNITY + r" {proper caps username}" + ": Sets a user to the community list of streamers.\n"
    msg += p + Commands.REMOVE + r" {proper caps username}" + ": Removes a user from the streamer database.\n\n"
    msg += p + Commands.EMBED + r" {0: disable, 1: enable}" + ": Toggles use of embeds.\n\n"

    msg += "For reactions, thumbs up means a successful add, while a thumbs down likely means the user doesn't exist."
    return msg

# Helper method to convert a tuple to a string.
def convertTuple(tup): 
    return ''.join(tup)

client.run(Config.TOKEN)