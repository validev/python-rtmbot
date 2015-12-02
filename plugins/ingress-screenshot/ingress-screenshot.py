import time, subprocess, tempfile, os, slacker, geopy, geopy.distance, pprint

crontable = []
outputs = []

slack = None
my_uid = None
users = {}
plugindir = None
slacktoken = None

def setup(given_bot):
    global slack, my_uid, users, plugindir, slacktoken
    print("ingress-screenshot: setup()")
    slack = given_bot.slack_client
    my_uid = slack.server.login_data['self']['id']
    for u in slack.server.login_data['users']:
        users[u['id']] = u
    plugindir = os.path.dirname(__file__)
    if plugindir == "":
        plugindir = "."
    slacktoken = given_bot.token

def help(channel, username=None, error=None, manpage=False):
    global slack, my_uid, users
    if not manpage:
        message = 'Usage: @%s (m)iitc IntelURL|address' % users[my_uid]['name']
    else:
        message = 'Manpage @%s\n' % users[my_uid]['name']
        message += 'IITC Screenshot: @%s (m|p)iitc IntelURL|address\n' % users[my_uid]['name']
        message += 'IITC zooomed in: @%s (m|p)zoom IntelURL|address\n' % users[my_uid]['name']
        message += 'Stock Intel: @%s (m)intel|(m)screenshot IntelURL|address\n' % users[my_uid]['name']
        message += 'High Def: @%s (m|p)8k IntelURL|address\n' % users[my_uid]['name']
        message += 'Regions: @%s europe|europa|asien|asia|world|welt\n' % users[my_uid]['name']
        message += 'Help: @%s help|hilfe|manpage\n' % users[my_uid]['name']
        message += '(m: for mobile devices)\n'
        message += 'Beware: Stock Intel shots take more time and are sometimes incomplete.'
        
    if error:
        message = 'ERROR: %s\n\n%s' % (error, message)
    if username:
        message = '@%s %s' % (username, message)
    slack.api_call('chat.postMessage', channel=channel, text=message, as_user=True, link_names=True)

def process_message(data):
    global slack, my_uid, users, plugindir, slacktoken
    
    if not 'text' in data or not ('user' in data or 'bot_id' in data):
        # print('ingress-screenshot: no "text", "user" or "bot_id" in data: %s' % str(data))
        return

    timestamp = data['ts']
    message = data['text']
    # human user?
    if 'user' in data:
        is_bot = False
        sender_uid = data['user']
        if not sender_uid.startswith('U'):
            print('ingress-screenshot: User detected but user id starts not with U (%s)' % sender_uid)
    # bot user?
    elif 'bot_id' in data:
        is_bot = True
        sender_uid = data['bot_id']
        if not sender_uid.startswith('B'):
            print('ingress-screenshot: Bot detected but bot_id  starts not with B (%s)' % sender_uid)
        #else:
            # print('ingress-screenshot: Bot detected %s' % str(data))
    else:
        print('ingress-screenshot: neither user nor bot detected')
        return
    if sender_uid in users:
        username = users[sender_uid]['name']
    elif 'username' in data:
        username = data['username']
    else: 
        print('ingress-screenshot: not a bot nor could I find user with id %s' % str(sender_uid))
        # help(channel, error='Could not find user with id %s' % str(sender_uid))
        return

    channel = None
    if 'channel' in data:
        channel = data['channel']
        #channel_info = slack.api_call("channels.info", channel=channel)
        channel_info=slack.server.channels.find(channel)
        channel_name=channel_info.name
        channel_id=channel_info.id
    elif 'group' in data:
        # Deprecated?? Kommt nicht vor. Auch Groups haben "channel" in data
        channel = data['group']
        #channel_info = slack.api_call("groups.info", channel=channel)
        channel_info=slack.server.channels.find(channel)
        channel_name=channel_info.name
        channel_id=channel_info.id
    else:
        print('ingress-screenshot: no channel or group in data. exiting ...')
        return
    
    # Hab ich mich selbst angesprochen?
#    if sender_uid.startswith('%s' % my_uid):
    if sender_uid == my_uid:
        return

    # Bin ich angesprochen?
    #  Ich höre auf meine uid und für webhooks auch auf meinen namen
    if not message.startswith('<@%s> ' % my_uid) and not message.startswith('<@%s>: ' % my_uid) and \
            not message.startswith('<@%s> ' % users[my_uid]['name']) and not message.startswith('<@%s>: ' % users[my_uid]['name']) and \
            not message.startswith('<@%s|%s> ' % (my_uid,users[my_uid]['name'])) and not message.startswith('<@%s|%s>: ' % (my_uid,users[my_uid]['name'])):
        # Wurde ich im private Chat angesprochen?
        if channel_id.startswith('D'):
            message = '<@%s>: %s' % (my_uid, message)
        else:
            return
        
    # Ich darf nicht ist jedem Channel/jeder Group reden
    # bzw. ich darf in keinem Channel reden
    if channel_name == 'resmuc_all' or \
            channel_name == 'resmuc_offtopic' :
            #channel_id.startswith('C') :
        return

    # Block setzen
    tempfile.TemporaryFile()
    blockdirname = os.path.join(tempfile.tempdir, 'irmbot-semaphore-' + str(timestamp))
    try:
        os.mkdir(blockdirname)
    except Exception as e:
        return

    message = ' '.join(message.split())
    args = message.split(' ', 2)
    command = args[1]
    command = command.lower()
    if \
            command == 'help' or \
            command == 'manpage' or \
            command == 'man' or \
            command == 'hilfe' or \
            command == 'asia' or \
            command == 'asien' or \
            command == 'europe' or \
            command == 'europa' or \
            command == 'world' or \
            command == 'welt' or \
            command == 'screenshot' or \
            command == 'mscreenshot' or \
            command == 'intel' or \
            command == 'mintel' or \
            command == 'iitc' or \
            command == 'miitc' or \
            command == 'iitcm' or \
            command == 'zoom' or \
            command == 'mzoom' or \
            command == '8k' or \
            command == 'm8k' or \
            :

        # Typos
        if command == 'iitcm':
            command = 'miitc'

        iitc = '0'
        delay = '360'

        if len(args) < 3:
            if command == 'world' or command == 'welt':
                command = 'world'
                url = 'https://www.ingress.com/intel?ll=40.313043,3.691406&z=3'
                iitc = '1'
                delay = '30' 
            elif command == 'europe' or command == 'europa':
                command = 'europe'
                url = 'https://www.ingress.com/intel?ll=48.319734,8.591309&z=5'
                iitc = '1'
                delay = '30'
            elif command == 'asia' or command == 'asien':
                command = 'asia'
                url = 'https://www.ingress.com/intel?ll=44.590467,111.708984&z=4'
                iitc = '1'
                delay = '30'
            elif command == 'help' or command == 'hilfe':
                help(channel, username)
                return
            elif command == 'manpage' or command == 'man':
                help(channel, username, manpage=True)
                return
            else:
                help(channel, username, 'Syntax error.')
                return
        elif args[2] == '':
            print('ingress-screenshot: no url/address given')
            help(channel, username, 'No url/address given')
            return
        elif args[2].startswith('<http'):
            url = args[2][1:-1]
            if not url.startswith('http://www.ingress.com/intel?') and not url.startswith('https://www.ingress.com/intel?'):
                help(channel, username, 'No valid intel url given')
                return
        else:
            url = ''

        # Defaults:
        # mobile bedeutet Ausgabe optimiert für Smartphones (JPG anstatt PNG, portrait anstatt landscape)
        mobile = '0'
        # Standardauflösung
        x_resolution = '1920'
        y_resolution = '1080'

        if command == 'iitc' or command == 'zoom' or command == 'miitc' or command == 'mzoom' :
            iitc = '1'
            delay = '30'
        if command == '8k' or command == 'm8k':
            # 8k Bilder grundsätzlich als .JPG wegen der Groesse
            mobile = '1'
            iitc = '1'
            delay = '90'
            x_resolution = '7680'
            y_resolution = '4320'
        if command.startswith('m'):
            mobile = '1'
            y_resolution,x_resolution = x_resolution,y_resolution

        if not url:
            try:
                geo = geopy.geocoders.GoogleV3()
                loc = geo.geocode(args[2])
                print('ingress-screenshot: Search Result for "%s":\n%s' % (args[2], pprint.pformat(loc.raw)))
                lat = loc.latitude
                lng = loc.longitude
                ne = loc.raw['geometry']['viewport']['northeast']
                sw = loc.raw['geometry']['viewport']['southwest']
                distance = geopy.distance.vincenty((ne['lat'], ne['lng']), (sw['lat'], sw['lng'])).meters
                if command == 'zoom' or command == 'mzoom' or \
                        command == '8k' or command == 'm8k' :
                    # all portals visible
                    zoom = 15
                else:
                    # zoom dependend of requested locality
                    zoom = 10
                    if distance < 3000:
                        # Elversberg
                        zoom = 16
                    elif distance < 10000:
                        # St. Ingbert
                        zoom = 15
                    elif distance < 30000:
                        # Saarbruecken
                        zoom = 14
                    elif distance < 60000:
                        # Region Saarbruecken
                        zoom = 13
                    elif distance < 90000:
                        # main Saarland
                        zoom = 12
                    elif distance < 120000:
                        # full Saarland
                        zoom = 11
                    elif distance < 200000:
                        # Rheinland-Pfalz?
                        zoom = 10
                    elif distance < 400000:
                        # half Germany
                        zoom = 9
                    elif distance < 800000:
                        # almost Germany
                        zoom = 8
                    elif distance < 1200000:
                        # full? Germany
                        zoom = 7
                    elif distance >= 1200000:
                        # ???
                        zoom = 5

                print('ingress-screenshot: boundary distance: %d m => zoom level %d' % (distance, zoom))
                url = 'https://www.ingress.com/intel?ll=%f,%f&z=%d' % (lat, lng, zoom)
                requested_location = '_%s_ %s' % (loc.address, url)
                # Zeitanpassung an die Zoomstufe bei Stock Intel
                if iitc == '0':
                    maxzoom = 16
                    variabletime = int(delay) - 30
                    fraction = variabletime / maxzoom
                    deltazoom = maxzoom - int(zoom)
                    timedecrease = variabletime - int(deltazoom * fraction)
                    delay = str(int(delay) - timedecrease)

            except Exception as e:
                print('ingress-screenshot: error parsing location result for "%s": %s' % (url, e))
                help(channel, username, 'Could not parse location search result for "%s": %s' % (url, e))
                return
        else:
            requested_location = url

        print('ingress-screenshot: Creating screenshot of %s on request of %s in channel %s' % (url, username, channel_info.name))
        tmpdir = tempfile.mkdtemp(prefix='ingress-screenshot-')
        if mobile == '1':
            tmpfilename = command+'.jpg'
        else:
            tmpfilename = command+'.png'
        screenshotfile = os.path.join(tmpdir, tmpfilename)

        message = 'Aye aye. Generating screenshot ...'
        if username:
            message = '@%s %s' % (username, message)
            slack.api_call('chat.postMessage', channel=channel, text=message, as_user=True, link_names=True)

        if is_bot:
            ice_file = 'ice.js'
        else:
            ice_file = 'ice_playertracker.js'

        # 1 username password https://www.ingress.com/intel?ll=49.25544,7.041324&z=16 1 8 60 1920 1080 ./ 0 0 1
        cmd = [
            "phantomjs", "--web-security=false", "--ignore-ssl-errors=true",
            "--cookies-file="+os.path.join(plugindir, "phantomjs.cookies"),
            '--disk-cache=true', '--max-disk-cache-size=1000000',
            os.path.join(plugindir, ice_file),
            '1', '', '', url, '1', '8', delay, x_resolution, y_resolution,
            screenshotfile,
            '2', iitc, '1'
            ]
        print('ingress-screenshot: "'+'" "'.join(cmd)+'"')

        # Drei Versuche, PhantomJS aufzurufen, da er manchmal ohne erkennbaren Grund failed
        i = 0
        while True:
            i = i + 1
            if subprocess.call(cmd) != 0:
                print('ingress-screenshot: failed to run phantomjs')
                if i == 3:
                    help(channel, username, 'Failed to run phantomjs, contact admin')
                    return
                else:
                    time.sleep(3*10)
            else:
                break

        print('ingress-screenshot: optimizing screenshot')
        if mobile == '1':
            cmd = [ "jpegoptim", "--quiet", "-m35", screenshotfile ]
        else:
            cmd = [ "optipng", "--quiet", "-o1", screenshotfile ]
        if subprocess.call(cmd) != 0:
            print('ingress-screenshot: failed to optimize screenshot')
            help(channel, username, 'Failed to optimize screenshot, contact admin')
            return

        print('ingress-screenshot: sending screenshot to slack using slacker')
        try:
            slacker_client = slacker.Slacker(slacktoken)
            response = slacker_client.files.upload(screenshotfile,
                                                   initial_comment='@%s, here is your screenshot of %s' % (username, requested_location),
                                                   channels=channel)
            if 'file' in response.body:
                del(response.body['file'])
            print('ingress-screenshot: response=%s' % str(response.body))
        except Exception as e:
            print('ingress-screenshot: got exception from slacker: %s' % str(e))
            
    else:
        help(channel, username, 'Syntax error.')

# Gibt Probleme bei mehreren gestarteten Instanzen
#    try:
#        os.rmdir(blockdirname)
#    except Exception as e:
#        print('ingress-screenshot: cannot remove blockdir: %s' % str(e))
 
    return

