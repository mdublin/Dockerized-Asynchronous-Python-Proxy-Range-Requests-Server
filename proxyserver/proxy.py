from aiohttp import web, ClientSession, TCPConnector
import jinja2
import aiohttp_jinja2
import asyncio
from time import mktime, time
from wsgiref.handlers import format_date_time
from datetime import datetime
import re


# for HEAD request
async def fetch_head(url, resp):
    async with resp.head(url) as headresponse:
        # return await response.read()
        app["headresponsedata"] = headresponse
        return await headresponse.read()

async def bound_fetch_head(sem, url, resp):
    # Getter function with semaphore.
    async with sem:
        await fetch_head(url, resp)


# for GET request with range Headers
async def fetch(url, resp, headers):
    async with resp.get(url, headers=headers) as response:
        app["responsedata"] = response
        app["responsedata_bytedata"] = await response.read()
        return await response.read()

async def bound_fetch(sem, url, resp, headers):
    # Getter function with semaphore.
    async with sem:
        await fetch(url, resp, headers)


async def index(request):
    print("Proxy receiving request: ")
    print(request.headers)
    # multipart range requests via headers or query string can just be passed to
    # app server, but we still have to parse out for congruity checks

    tasks = []

    def hop_by_hop_cleanup(request_headers):

        for key, value in request_headers.items():
            print(key, value)

        hop_by_hop_headers = [
            'Connection',
            'Transfer-Encoding',
            'TE',
            'Keep-Alive',
            'Proxy-Authentication',
            'Trailer',
            'Upgrade',
            'Proxy-Authorization']

        revised_request_headers = {
            k: v for (
                k, v) in request_headers.items() if not any(
                hopheader in k for hopheader in hop_by_hop_headers)}

        return revised_request_headers

    # break up range parameters for congruity check, mostly in case of
    # multiple range requests
    def listify_ranges(rangeparams):
        ranges = []
        # for Range header
        if isinstance(rangeparams, str):
            rangeparams = re.findall(r"[\w']+", rangeparams)
        # yes, it is a Big O of n**2 but assuming amount of range params in case of multiple
        # range request will be reasonably nominal
        for item in rangeparams:
            byterange = item.split("-")
            for i in byterange:
                ranges.append(i)
        return ranges

    # range query param check
    if request.query != {}:
        # using values to get values of query strings with duplicate keys (e.g.
        # http://0.0.0.0:8989/?range=100-2000&range=300-4000)
        if len(request.query.values()) > 1:
            range_query = ", ".join([x for x in request.query.values()])
        else:
            range_query = request.query
            range_query = range_query["range"]
    else:
        range_query = None

    # clean up client request headers before forwarding application server
    headers = hop_by_hop_cleanup(request.headers)

    # checking for presence of Range header in request.headers
    for index, item in enumerate(headers):
        if 'Range' in item:

            client_range_request_header = listify_ranges(
                headers["Range"].replace("bytes=", ""))
        else:
            client_range_request_header = None

    # if range query string and Range header are both present, check for
    # congruity
    if client_range_request_header and range_query:
        print("checking range requests congruity...")
        if client_range_request_header == range_query:
            print("header and query param congruity check: passed")
        else:
            print("returning 416 response")
            bad_range_response = web.Response(
                status=416, reason='Range Not Satisfiable')
            bad_range_response.headers['Content-Range'] = '*/'
            bad_range_response.headers['Via'] = 'MyProxyServer 1.0'
            return bad_range_response

    # using range query string and adding as Range header
    elif range_query and not client_range_request_header:
        print("adding Range query param to header")
        headers["Range"] = "bytes={}".format(range_query)
        client_range_request_header = True
        print(client_range_request_header)
    # catching a potential HEAD or empty GET request
    elif range_query is None and client_range_request_header is None:

        # self-contained Response handler for HEAD requests and empty GET
        # requests
        if (request.method == "HEAD") or (request.method == 'GET'):
            print("HEAD or empty GET REQUEST MADE!!!!!")
            task = asyncio.ensure_future(
                bound_fetch_head(
                    sem,
                    'http://application-service:9090',
                    request.app["session"]))
            tasks.append(task)
        responses = asyncio.gather(*tasks)

        await responses

        status = app["headresponsedata"].status
        reason = app["headresponsedata"].reason
        non_stream_response = web.Response(status=status, reason=reason)

        print(app["headresponsedata"].headers.items())
        for key, value in app["headresponsedata"].headers.items():
            non_stream_response.headers[key] = value
        non_stream_response.headers['Via'] = 'MyProxyServer 1.0'
        await non_stream_response.prepare(request)
        return non_stream_response

    if client_range_request_header or (client_range_request_header is True):
        print("client_range_request_header: ")
        print(client_range_request_header)
        print(request.method)

        if (request.method == "GET"):
            task = asyncio.ensure_future(
                bound_fetch(
                    sem,
                    'http://application-service:9090',
                    request.app["session"],
                    headers))
            tasks.append(task)

        else:
            print("NOPE!!!")

        responses = asyncio.gather(*tasks)

        await responses

        status = app["responsedata"].status
        reason = app["responsedata"].reason
        stream = web.Response(status=status, reason=reason)

        for key, value in app["responsedata"].headers.items():
            stream.headers[key] = value

        stream.headers['Via'] = 'MyProxyServer 1.0'
        await stream.prepare(request)
        stream.write(app["responsedata_bytedata"])
        get_bytes_transferred(len(app["responsedata_bytedata"]))
        return stream

async def create_session():
    async with ClientSession() as session:
        app["session"] = session

# uptime callback


def get_current_uptime():
    uptime = time() - start_time
    uptime_readable = datetime.fromtimestamp(uptime)
    uptime_readble = uptime_readable.strftime('%H:%M:%S')
    nix_years = r"[\d+]+-[\d+]+-\d+"
    uptime_readable = (str(uptime_readable).split(
        re.search(nix_years, str(uptime_readable)).group()))[1]
    return uptime_readable

bytes_transferred = 0
# total bytes transferred callback


def get_bytes_transferred(bytedata):
    global bytes_transferred
    bytes_transferred = bytes_transferred + bytedata
    return bytes_transferred

# stats view
# http://0.0.0.0:8080/stats


@aiohttp_jinja2.template('test.jinja2')
async def stats(request):
    uptime = get_current_uptime()
    # byte count and uptime numbers in this dict, will render on jinja2
    # template
    context = {'totalbytes': bytes_transferred, 'uptime': uptime}
    response = aiohttp_jinja2.render_template('test.jinja2', request, context)
    return response


def setup_middlewares(app):
    error_middleware = error_pages({404: handle_404,
                                    500: handle_500})
    app.middlewares.append(error_middleware)


def setup_routes(app):
    app.router.add_get('/', index)
    app.router.add_get('/stats', stats)

if __name__ == '__main__':
    try:
        app = web.Application()
        # setting up jinja2 environment
        aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader('templates'))
        setup_routes(app)
        start_time = time()
        app["session"] = ClientSession(
            connector=TCPConnector(
                verify_ssl=False))
        sem = asyncio.Semaphore(1000)
        #web.run_app(app, host='0.0.0.0', port=8080)
        web.run_app(app, host='0.0.0.0', port=8080)


    except Exception as e:
        print("[!!!] There was a problem launching the proxy server: ")
        print(e)
