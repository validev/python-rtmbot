import datetime, time

crontable = []
outputs = []

slack = None
my_uid = None
users = {}

def setup(given_bot):
    global slack, my_uid, users
    print("ingress-septicycle: setup()")
    slack = given_bot.slack_client
    my_uid = slack.server.login_data['self']['id']
    for u in slack.server.login_data['users']:
        users[u['id']] = u

def help(channel, username=None, error=None):
    global slack, my_uid, users
    print('ingress-septicycle: help()')
    message = 'Usage: @%s septicycle [#checkpoints [YYYY-MM-DD]]' % users[my_uid]['name']
    if error:
        message = 'ERROR: %s\n\n%s' % (error, message)
    if username:
        message = '@%s %s' % (username, message)
    slack.api_call('chat.postMessage', channel=channel, text=message, as_user=True, link_names=True)


def process_message(data):
    global slack, my_uid, users
    print('ingress-septicycle: process_message()')
    
    if not 'text' in data or not 'user' in data:
        print('ingress-septicycle: no "text" or "user" in data: %s' % str(data))
        return

    message = data['text']
    sender_uid = data['user']
    if not sender_uid in users:
        print('ingress-septicycle: could not find user with id %s' % str(sender_uid))
        help(channel, message='Could not find user with id %s' % str(sender_uid))
        return
    username = users[sender_uid]['name']
    channel = None
    if 'channel' in data:
        channel = data['channel']
    elif 'group' in data:
        channel = data['group']

    if message.startswith('<@%s> septicycle' % my_uid) or \
            message.startswith('<@%s> cycle' % my_uid) or \
            message.startswith('<@%s>: septicycle' % my_uid) or \
            message.startswith('<@%s>: cycle' % my_uid) or \
            message.startswith('<@%s> checkpoint' % my_uid) or \
            message.startswith('<@%s>: checkpoint' % my_uid):
        args = message.split(' ')
        num_cps = 1
        start = time.time()
        cmd = args[1]
        if len(args) > 2:
            try:
                num_cps = int(args[2])
            except ValueError as e:
                print('ingress-septicycle: could not parse number of checkpoints: %s' % args[2])
                help(channel, username, 'Could not parse number of checkpoints: %s' % args[2])
                return
        if len(args) > 3:
            try:
                start = time.mktime(time.strptime(args[3], "%Y-%m-%d"))
                startappend = ' starting at %s' % args[3]
            except Exception as e:
                print('ingress-septicycle: could not parse start date: %s' % args[3])
                help(channel, username, 'Could not parse start date: %s' % args[3])
                return

        print('ingress-septicycle: Creating %d %s on request of %s in channel %s' % (num_cps, cmd, username, channel))
        sec_per_cycle = 7*25*60*60
        sec_per_checkpoint = 5*60*60
        cycle_start = int(start // sec_per_cycle) * sec_per_cycle
        
        cp = cycle_start+sec_per_checkpoint
        count = 0
        output = ''
        while count < num_cps:
            append = ''
            if cp == cycle_start+sec_per_cycle:
                append = ' *Septicycle End*'
                cycle_start = cp
            if cp >= start:
                count = count+1
                output = '%sCP: %s%s\n' % (output, str(datetime.datetime.fromtimestamp(cp))[:16], append)
            cp = cp+sec_per_checkpoint
        message = '@%s these are the next %d checkpoints%s:\n%s' % (username, num_cps, startappend, output)

        print('ingress-septicycle: sending results to slack')
        slack.api_call('chat.postMessage', channel=channel, text=message, as_user=True, link_names=True)

    return

