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

def help(channel, username=None, error=None):
    global slack, my_uid, users
    print('ingress-screenshot: help()')
    message = 'Usage: @%s screenshot IntelURL|address' % users[my_uid]['name']
    if error:
        message = 'ERROR: %s\n\n%s' % (error, message)
    if username:
        message = '@%s %s' % (username, message)
    slack.api_call('chat.postMessage', channel=channel, text=message, as_user=True, link_names=True)

def process_message(data):
    global slack, my_uid, users, plugindir, slacktoken
    
    if not 'text' in data or not 'user' in data:
        print('ingress-screenshot: no "text" or "user" in data: %s' % str(data))
        return
    message = data['text']
    sender_uid = data['user']
    if not sender_uid in users:
        print('ingress-screenshot: could not find user with id %s' % str(sender_uid))
        help(channel, message='Could not find user with id %s' % str(sender_uid))
        return
    username = users[sender_uid]['name']
    channel = None
    if 'channel' in data:
        channel = data['channel']
    elif 'group' in data:
        channel = data['group']
    if message.startswith('<@%s> screenshot ' % my_uid) or \
            message.startswith('<@%s>: screenshot ' % my_uid):
        args = message.split(' ', 2)
        url = args[2]
        if url == '':
            print('ingress-screenshot: no url/address given')
            help(channel, message='No url/address given')
            return
        if not url.startswith('<http'):
            try:
                geo = geopy.geocoders.GoogleV3()
                loc = geo.geocode(url)
                print('ingress-screenshot: Search Result for "%s":\n%s' % (url, pprint.pformat(loc.raw)))
                lat = loc.latitude
                lng = loc.longitude
                ne = loc.raw['geometry']['viewport']['northeast']
                sw = loc.raw['geometry']['viewport']['southwest']
                distance = geopy.distance.vincenty((ne['lat'], ne['lng']), (sw['lat'], sw['lng'])).meters
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
            except Exception as e:
                print('ingress-screenshot: error parsing location result for "%s": %s' % (url, e))
                help(channel, username, 'Could not parse location search result for "%s": %s' % (url, e))
                return
        else:
            url = url[1:-1]
            requested_location = url

        print('ingress-screenshot: Creating screenshot of %s on request of %s in channel %s' % (url, username, channel))
        tmpdir = tempfile.mkdtemp(prefix='ingress-screenshot-')
        screenshotfile = os.path.join(tmpdir, 'screenshot.png')
        cmd = [
            "phantomjs",
            os.path.join(plugindir, "ice.js"),
            '', '', url, '1', '8', '5', '1920', '1080',
            screenshotfile,
            '1', '4'
            ]
        print('ingress-screenshot: "'+'" "'.join(cmd)+'"')
        if subprocess.call(cmd) != 0:
            print('ingress-screenshot: failed to run phantomjs')
            help(channel, username, 'Failed to run phantomjs, contact admin')
            return

        print('ingress-screenshot: sending screenshot to slack using slacker')
        try:
            slacker_client = slacker.Slacker(slacktoken)
            response = slacker_client.files.upload(screenshotfile,
                                                   initial_comment='@%s hier ist dein Screenshot von %s' % (username, requested_location),
                                                   channels=channel)
            if 'file' in response.body:
                del(response.body['file'])
            print('ingress-screenshot: response=%s' % str(response.body))
        except Exception as e:
            print('ingress-screenshot: got exception from slacker: %s' % str(e))
    return

