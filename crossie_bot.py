import gspread
from oauth2client.service_account import ServiceAccountCredentials
from webwhatsapi import WhatsAPIDriver
import re
import time
from pprint import pprint

################# Some globals ###############

TIME_BETWEEN_UPDATES = 3 # in seconds
NEW_CHATFILE_NAME = './chats/new_chat'
OLD_CHATFILE_NAME = './chats/old_chat'
OLDER_CHATFILE_NAME = './chats/older_chat'
GROUP_ID = '919962301632-1494342185@g.us'
SACHIN_CHAT_ID = '919962126770@c.us'
BUT_WHY_LINK = 'https://www.youtube.com/watch?v=K4smXP46tG4'
SHEET_LINK = 'https://docs.google.com/spreadsheets/d/1n1fAjkz6VnBuTZNX1Hh9zQZhKoblquf-FBxOTuIgs1o/edit#gid=0'

####### The help string #######

HELP_STRING = '*Crossie bot help*' + \
'\n\n' + \
'Hi there, this is crossie bot! ' + \
'I keep track of the clues posted on this group, ' + \
'but I can also do a few others things.' + \
'\n\n' + \
'All clues from this group (and older ones) are archived at ' + \
SHEET_LINK + ' (editable sheet). If you do not find your clue there within a day of posting, ' + \
'be sure to ask Sachin about it.' + \
'\n\n' + \
'*Messages I respond to (case insensitive)*' + \
'\n\n' + \
'@919008433618 how2' + \
'\n' + \
'_I display this help message._' + \
'\n\n' + \
'But why' + \
'\n' + \
'_I send a link to a YouTube video._' + \
'\n\n' + \
'@(phone number) RTS' + \
'\n' + \
'_I give away an RTS! For further information on RTS, ask Rakesh._' + \
'\n\n' + \
'@919008433618 RTS tally' + \
'\n' + \
'_I display the current RTS tally._' + \
'\n\n' + \
'*FAQs*' + \
'\n\n' + \
'How do you know know when a message is a clue?' + \
'\n\n' + \
'_I look for text followed by numbers enclosed in (parantheses). ' + \
'Multiple clues in a single message is fine too. Anything after the ' + \
'enum of the last clue in a message is ignored. ' + \
'Clues that span multiple lines are currently unsupported and will not be archived._' + \
'\n\n' + \
'Why aren\'t you working fine?' + \
'\n\n' + \
'_Usually the most likely reason is that there\'s a power or internet outage here. ' + \
'Response times should typically be 5 seconds or less, so don\'t bother waiting for me. ' + \
'You can blame Sachin, he keeps tinkering with me._'

##############################################
###### Where all the regex magic happens #####
##############################################

clue_regex = re.compile(r"""
	.+ # The clue could be any (non empty) string
	\( # Opening parenthesis
	[0-9]* # Single number for enum
	(
		(,|\.|\-|/)(\ *) # Separators for enum
		[0-9]* # Potentially more numbers in enum
	)* # But we do not know how many more
	\) # Close parenthesis
	""", re.VERBOSE)

add_RTS_regex = re.compile(r"""
	\@([0-9]*) # @phone_number
	(\s*) # Any amount of space
	rts # RTS!
	(\s*) # Any amount of space
	$ # If we dont match the end of string, RTS tally gets included too
	""", re.VERBOSE)

query_RTS_regex = re.compile(r"""
	\@(919008433618) # @crossie_bot
	(\s*) # Any amount of space
	rts(\s*)tally # RTS!
	""", re.VERBOSE)

help_regex = re.compile(r"""
	\@(919008433618) # @crossie_bot
	(\s*) # any amount of space
	how2 # how2 indeed
	(\s*) # any amount of space
	""", re.VERBOSE)

but_why_regex = re.compile(r"""
	but
	(\s*) # any amount of space
	why
	(\?)?
	""", re.VERBOSE)

##############################################
########### A few helper functions ###########
##############################################

def isnewmessage(line):
	if len(line) < 10:
		return False
	if ',' not in line:
		return False
	date = line.split(',')[0]
	if len(date.split('/')) == 3:
		return True
	return False

def get_clues(msg_string):
	clues = []
	if any([char in msg_string for char in '}{[]']):
		return clues
	while True:
		match = clue_regex.match(msg_string.strip())
		if match is None:
			break
		curr_clue = match.group()
		clue_size = len(curr_clue)
		clues.append(curr_clue)
		msg_string = msg_string[clue_size : ].strip()
	return clues

def format_timestamp(ts):
	# yyyy-mm-dd hh:mm:ss --> mm/dd/yyyy, hh:mm
	date, time = ts.split()

	# Formatting time
	fmt_time = None
	hh, mm, ss = map(int, time.split(':'))
	if hh >= 12:
		hh -= 12
		if hh == 0:
			hh = 12
		fmt_time = str(hh) + ':' + str(mm).zfill(2) + ' PM'
	else:
		if hh == 0:
			hh = 12
		fmt_time = str(hh) + ':' + str(mm).zfill(2) + ' AM'

	y, m, d = map(int, date.split('-'))
	fmt_date = '/'.join([str(m), str(d), str(y % 100)])
	return fmt_date + ', ' + fmt_time

##############################################
######## Heavier lifing happens here #########
##############################################

def get_clues_from_file(filename):
	msg_date, msg_time, msg_sender, msg_string = '', '', '', ''
	all_clues = []

	with open(filename) as f:
		for line in f:
			line = line.strip()
			if isnewmessage(line):
				for clue in get_clues(msg_string):
					all_clues.append((msg_date, msg_time, msg_sender, clue))
				msg_date = line.split(',')[0].strip()
				line = ','.join(line.split(',')[1:])
				msg_time = line.split('-')[0].strip()
				line = '-'.join(line.split('-')[1:])
				msg_sender = line.split(':')[0].strip()
				line = ':'.join(line.split(':')[1:])
				msg_string = line.strip()
			else:
				msg_string += ("\n" + line.strip())

	return all_clues

def make_unique(all_clues):
	seen_clues = set()
	unique_clues = []
	for c in all_clues:
		if c[3] not in seen_clues:
			seen_clues.add(c[3])
			unique_clues.append(c)
	return unique_clues

def get_RTS_from_file(filename):
	all_RTS = {}

	with open(filename) as f:
		for line in f:
			line = line.strip()
			if isnewmessage(line):
				msg_string = ''.join(line.split('- ')[1:])
				msg_string = ''.join(msg_string.split(': ')[1:])
				match = add_RTS_regex.match(msg_string.lower().strip())
				if match is None:
					continue

				RTS_person = match.group(1)
				if RTS_person not in all_RTS:
					all_RTS[RTS_person] = 0
				all_RTS[RTS_person] += 1

	return sorted(all_RTS.items())

def push_clues_to_sheet(clues):
	n_clues = len(clues)
	print('\tConnecting to Google Sheets')

	scope = ['https://spreadsheets.google.com/feeds',
			 'https://www.googleapis.com/auth/drive']

	credentials = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
	gc = gspread.authorize(credentials)
	wks = gc.open("Crossie clues")
	sheet = wks.sheet1

	print('\tConnection successful')
	print('\tPushing clues to Google sheets')

	row_f = 2
	row_l = 1 + n_clues
	col_f = 1
	col_l = 4

	cell_range = sheet.range(row_f, col_f, row_l, col_l)

	for cell in cell_range:
		i = cell.row - 2
		j = cell.col - 1
		cell.value = clues[i][j]
		
	print('\tMaking updates')
	sheet.update_cells(cell_range)

##############################################
############# The main event loop ############
##############################################

if __name__ == '__main__':
	driver = WhatsAPIDriver()
	print("Waiting for QR")
	driver.wait_for_login()
	print("Bot started")

	epoch = 1

	print('Making initial update')
	new_clues = get_clues_from_file(NEW_CHATFILE_NAME)
	old_clues = get_clues_from_file(OLD_CHATFILE_NAME)
	older_clues = get_clues_from_file(OLDER_CHATFILE_NAME)
	all_clues = make_unique(older_clues + old_clues + new_clues)
	push_clues_to_sheet(all_clues)
	print('Done')

	while True:
		time.sleep(TIME_BETWEEN_UPDATES)
		flag = False
		print("Beep " + str(epoch))
		unread = driver.get_unread()
		for message_group in unread:
			if message_group.chat.id == GROUP_ID:
				flag = True
				with open(NEW_CHATFILE_NAME, 'a+') as chat_file:
					for m in message_group.messages:
						# Checking and updating sheet
						print(m)
						fmt_ts = format_timestamp(str(m.timestamp))
						chat_file.write(fmt_ts)
						chat_file.write(" - ")
						chat_file.write(str(m.sender.get_safe_name()))
						chat_file.write(": ")
						chat_file.write(str(m.content))
						chat_file.write("\n")


						# RTS query
						query_RTS_match = query_RTS_regex.match(str(m.content).lower())
						if query_RTS_match is not None:
							RTS_tally = get_RTS_from_file(NEW_CHATFILE_NAME)
							RTS_message = '*Current RTS tally*\n\n'
							if len(RTS_tally) == 0:
								RTS_message += "It's empty lol"
							else:
								for person, tally in RTS_tally:
									RTS_message += '@' + person + ": " + str(tally) + '\n'
							driver.send_message_to_id(GROUP_ID, RTS_message)

						# Someone got an RTS!
						add_RTS_match = add_RTS_regex.match(str(m.content).lower())
						if add_RTS_match is not None:
							RTS_person = add_RTS_match.group(1)
							RTS_message = '@' + RTS_person + ' Congrats! You got an RTS :D'
							driver.send_message_to_id(GROUP_ID, RTS_message)

						# Help section
						help_match = help_regex.match(str(m.content).lower())
						if help_match is not None:
							driver.send_message_to_id(GROUP_ID, HELP_STRING)

						# But why
						but_why_match = but_why_regex.match(str(m.content).lower())
						if but_why_match is not None:
							driver.send_message_to_id(GROUP_ID, BUT_WHY_LINK)

		if flag:
			new_clues = get_clues_from_file(NEW_CHATFILE_NAME)
			old_clues = get_clues_from_file(OLD_CHATFILE_NAME)
			all_clues = make_unique(old_clues + new_clues)
			push_clues_to_sheet(all_clues)
		epoch += 1
