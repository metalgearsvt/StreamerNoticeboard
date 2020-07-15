import sqlite3

conn = sqlite3.connect('noticeboard.db')

print('Please paste the channel ID to listen on: ')
channel = input()

c = conn.cursor()
c.execute('''CREATE TABLE "streamers" (
	"username"	TEXT NOT NULL,
	"type"	TEXT NOT NULL,
	"broadcast_id"	TEXT NOT NULL,
	"display_name"	TEXT NOT NULL,
	PRIMARY KEY("broadcast_id")
)''')

c.execute('''CREATE TABLE "settings" (
	"name"	TEXT NOT NULL,
	"value"	TEXT,
	PRIMARY KEY("name")
)''')

c.execute('''INSERT INTO "main"."settings"("name","value") VALUES ("prefix","!")''')

c.execute('''INSERT INTO "main"."settings"("name","value") VALUES ("noticechannel","''' + channel + '''")''')

c.execute('''INSERT INTO "main"."settings"("name","value") VALUES ("noticeboard_id","0")''')

c.execute('''INSERT INTO "main"."settings"("name","value") VALUES ("embedmode","0")''')

conn.commit()
conn.close()