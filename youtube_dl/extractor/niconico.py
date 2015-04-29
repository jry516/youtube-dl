# encoding: utf-8
from __future__ import unicode_literals

import re
import json

from .common import InfoExtractor
from ..compat import (
    compat_urllib_parse,
    compat_urllib_request,
    compat_urlparse,
)
from ..utils import (
    ExtractorError,
    int_or_none,
    parse_duration,
    parse_iso8601,
    xpath_text,
    determine_ext,
)


class NiconicoIE(InfoExtractor):
    IE_NAME = 'niconico'
    IE_DESC = 'ニコニコ動画'

    _TESTS = [{
        'url': 'http://www.nicovideo.jp/watch/sm22312215',
        'md5': 'd1a75c0823e2f629128c43e1212760f9',
        'info_dict': {
            'id': 'sm22312215',
            'ext': 'mp4',
            'title': 'Big Buck Bunny',
            'uploader': 'takuya0301',
            'uploader_id': '2698420',
            'upload_date': '20131123',
            'timestamp': 1385182762,
            'description': '(c) copyright 2008, Blender Foundation / www.bigbuckbunny.org',
            'duration': 33,
        },
        'params': {
            'username': 'ydl.niconico@gmail.com',
            'password': 'youtube-dl',
        },
    }, {
        'url': 'http://www.nicovideo.jp/watch/nm14296458',
        'md5': '8db08e0158457cf852a31519fceea5bc',
        'info_dict': {
            'id': 'nm14296458',
            'ext': 'swf',
            'title': '【鏡音リン】Dance on media【オリジナル】take2!',
            'description': 'md5:689f066d74610b3b22e0f1739add0f58',
            'uploader': 'りょうた',
            'uploader_id': '18822557',
            'upload_date': '20110429',
            'timestamp': 1304065916,
            'duration': 209,
        },
        'params': {
            'username': 'ydl.niconico@gmail.com',
            'password': 'youtube-dl',
        },
    }, {
        # 'video exists but is marked as "deleted"
        'url': 'http://www.nicovideo.jp/watch/sm10000',
        'md5': '38e53c9aad548f3ecf01ca7680b59b08',
        'info_dict': {
            'id': 'sm10000',
            'ext': 'unknown_video',
            'description': 'deleted',
            'title': 'ドラえもんエターナル第3話「決戦第3新東京市」＜前編＞',
        },
        'params': {
            'username': 'ydl.niconico@gmail.com',
            'password': 'youtube-dl',
        }
    }]

    _VALID_URL = r'https?://(?:www\.|secure\.)?nicovideo\.jp/watch/(?P<id>(?:[a-z]{2})?[0-9]+)'
    _NETRC_MACHINE = 'niconico'
    # Determine whether the downloader used authentication to download video
    _AUTHENTICATED = False

    def _real_initialize(self):
        self._login()

    def _login(self):
        (username, password) = self._get_login_info()
        # No authentication to be performed
        if not username:
            return True

        # Log in
        login_form_strs = {
            'mail': username,
            'password': password,
        }
        # Convert to UTF-8 *before* urlencode because Python 2.x's urlencode
        # chokes on unicode
        login_form = dict((k.encode('utf-8'), v.encode('utf-8')) for k, v in login_form_strs.items())
        login_data = compat_urllib_parse.urlencode(login_form).encode('utf-8')
        request = compat_urllib_request.Request(
            'https://secure.nicovideo.jp/secure/login', login_data)
        login_results = self._download_webpage(
            request, None, note='Logging in', errnote='Unable to log in')
        if re.search(r'(?i)<h1 class="mb8p4">Log in error</h1>', login_results) is not None:
            self._downloader.report_warning('unable to log in: bad username or password')
            return False
        # Successful login
        self._AUTHENTICATED = True
        return True

    def _real_extract(self, url):
        video_id = self._match_id(url)

        # Get video webpage. We are not actually interested in it for normal
        # cases, but need the cookies in order to be able to download the
        # info webpage
        webpage = self._download_webpage('http://www.nicovideo.jp/watch/' + video_id, video_id)

        video_info = self._download_xml(
            'http://ext.nicovideo.jp/api/getthumbinfo/' + video_id, video_id,
            note='Downloading video info page')

        if self._AUTHENTICATED:
            # Get flv info
            flv_info_webpage = self._download_webpage(
                'http://flapi.nicovideo.jp/api/getflv/' + video_id + '?as3=1',
                video_id, 'Downloading flv info')
        else:
            # Get external player info
            ext_player_info = self._download_webpage(
                'http://ext.nicovideo.jp/thumb_watch/' + video_id, video_id)
            thumb_play_key = self._search_regex(
                r'\'thumbPlayKey\'\s*:\s*\'(.*?)\'', ext_player_info, 'thumbPlayKey')

            # Get flv info
            flv_info_data = compat_urllib_parse.urlencode({
                'k': thumb_play_key,
                'v': video_id
            })
            flv_info_request = compat_urllib_request.Request(
                'http://ext.nicovideo.jp/thumb_watch', flv_info_data,
                {'Content-Type': 'application/x-www-form-urlencoded'})
            flv_info_webpage = self._download_webpage(
                flv_info_request, video_id,
                note='Downloading flv info', errnote='Unable to download flv info')

        flv_info = compat_urlparse.parse_qs(flv_info_webpage)
        if 'url' not in flv_info:
            if 'deleted' in flv_info:
                raise ExtractorError('The video has been deleted.',
                                     expected=True)
            else:
                raise ExtractorError('Unable to find video URL')

        video_real_url = flv_info['url'][0]

        # Start extracting information
        title = xpath_text(video_info, './/title')
        if not title:
            title = self._html_search_regex(
                r'<span[^>]+class="videoHeaderTitle"[^>]*>([^<]+)</span>',
                webpage, 'video title')

        extension = xpath_text(video_info, './/movie_type')
        if not extension:
            extension = determine_ext(video_real_url)
        video_format = extension.upper()
        thumbnail = xpath_text(video_info, './/thumbnail_url')
        description = xpath_text(video_info, './/description')
        timestamp = parse_iso8601(xpath_text(video_info, './/first_retrieve'))
        view_count = int_or_none(xpath_text(video_info, './/view_counter'))
        comment_count = int_or_none(xpath_text(video_info, './/comment_num'))
        duration = parse_duration(xpath_text(video_info, './/length'))
        webpage_url = xpath_text(video_info, './/watch_url')

        if video_info.find('.//ch_id') is not None:
            uploader_id = video_info.find('.//ch_id').text
            uploader = video_info.find('.//ch_name').text
        elif video_info.find('.//user_id') is not None:
            uploader_id = video_info.find('.//user_id').text
            uploader = video_info.find('.//user_nickname').text
        else:
            uploader_id = uploader = None

        ret = {
            'id': video_id,
            'url': video_real_url,
            'title': title,
            'ext': extension,
            'format': video_format,
            'thumbnail': thumbnail,
            'description': description,
            'uploader': uploader,
            'timestamp': timestamp,
            'uploader_id': uploader_id,
            'view_count': view_count,
            'comment_count': comment_count,
            'duration': duration,
            'webpage_url': webpage_url,
        }
        return dict((k, v) for k, v in ret.items() if v is not None)


class NiconicoPlaylistIE(InfoExtractor):
    _VALID_URL = r'https?://www\.nicovideo\.jp/mylist/(?P<id>\d+)'

    _TEST = {
        'url': 'http://www.nicovideo.jp/mylist/27411728',
        'info_dict': {
            'id': '27411728',
            'title': 'AKB48のオールナイトニッポン',
        },
        'playlist_mincount': 225,
    }

    def _real_extract(self, url):
        list_id = self._match_id(url)
        webpage = self._download_webpage(url, list_id)

        entries_json = self._search_regex(r'Mylist\.preload\(\d+, (\[.*\])\);',
                                          webpage, 'entries')
        entries = json.loads(entries_json)
        entries = [{
            '_type': 'url',
            'ie_key': NiconicoIE.ie_key(),
            'url': ('http://www.nicovideo.jp/watch/%s' %
                    entry['item_data']['video_id']),
        } for entry in entries]

        return {
            '_type': 'playlist',
            'title': self._search_regex(r'\s+name: "(.*?)"', webpage, 'title'),
            'id': list_id,
            'entries': entries,
        }
