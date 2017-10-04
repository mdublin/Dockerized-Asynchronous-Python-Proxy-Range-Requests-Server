from aiohttp import web
import re


def bytesource(byte_range_request):

    # storing global-like variables in aiohttp app instance as key-value pairs
    app["multipart_response_header_check"] = False
    app["multipart_bytes_container"] = []

    # first and last bytes only request check
    first_and_last_bytes_header_pattern = r"bytes=0-0,-1"
    first_and_last_bytes_check = re.search(
        first_and_last_bytes_header_pattern, byte_range_request)

    # break up header string
    byte_range_request_list = [
        x for x in (
            byte_range_request.replace(
                "bytes=",
                "")).split("-") if x != '']

    # trying to catch various types of potential Range requests
    #
    # standard byte range request check
    if len(byte_range_request_list) == 2:
        try:
            return app["byteload"][
                int(byte_range_request_list[0]):int(byte_range_request_list[1])]

        except Exception as e:
            print("Error in bytesource: ")
            print(e)
    # multipart byte range request check
    elif len((byte_range_request.replace("bytes=", "")).split(", ")) >= 2:
        app["multipart_response_header_check"] = True
        multi_ranges = [
            x.split("-") for x in (byte_range_request.replace("bytes=", "")).split(", ")]
        # inserting various multipart byte range requests into list for parsing
        # during multipart response header construction
        for item in multi_ranges:
            app["multipart_bytes_container"].append(
                app["byteload"][int(item[0]):int(item[1])])
        return app["multipart_bytes_container"]

    # final byte request check
    elif len(byte_range_request_list) == 1:
        byte_range_request = int(byte_range_request_list[0].replace("-", ""))
        byteslicepoint = len(app["byteload"]) - byte_range_request_list
        return app["byteload"][byteslicepoint:]
    # first and last byte check
    elif first_and_last_bytes_check:
        return app["byteload"][0] + app["byteload"][len(app["byteload"]) - 1]
    else:
        return None


async def index(request):
    print("Application server receiving request from Proxy: ")
    print(request)
    print(request.headers)

    if (request.method == "HEAD"):
        contentlength = str(len(app["byteload"]))
        head_response = web.Response(status=200, reason='OK')
        head_response.headers["Content-Type"] = 'text/html; charset=utf-8'
        head_response.headers["Accept-Ranges"] = 'bytes'
        head_response.headers["Content-Length"] = contentlength

        await head_response.prepare(request)
        return head_response

    request_headers = request.headers
    for header, value in request_headers.items():
        if header == 'Range':
            bytedata_response = bytesource(value)
            status = 206

    stream = web.StreamResponse(status=status, reason='Partial Content')

    if app["multipart_response_header_check"]:
        boundary = '3d6b6a416f9b5\r\n'
        bytestring = ''
        for parts in app["multipart_bytes_container"]:
            bytestring = bytestring + boundary + "Content-Type: application/octet-stream\r\n" + \
                "Content-Range: bytes {}/{}\r\n".format(
                    (request.headers["Range"]).replace(
                        "bytes=", ""), len(
                        app["byteload"])) + parts.decode('utf-8')

        bytestring = bytestring.encode()
        stream.headers[
            "Content-Type"] = 'multipart/byteranges; boundary=3d6b6a416f9b5'
        stream.headers['Content-Length'] = '{}'.format(len(bytestring))
        await stream.prepare(request)
        stream.write(bytestring)
        stream.write_eof()
        return stream

    else:
        stream.headers['Content-Type'] = 'application/octet-stream'
        stream.headers['Content-Range'] = 'bytes {}/{}'.format(
            (request.headers["Range"]).replace(
                "bytes=", ""), len(
                app["byteload"]))
        stream.headers['Content-Length'] = '{}'.format(len(bytedata_response))
        await stream.prepare(request)
        stream.write(bytedata_response)
        stream.write_eof()
        return stream


def setup_middlewares(app):
    error_middleware = error_pages({404: handle_404,
                                    500: handle_500})
    app.middlewares.append(error_middleware)


def setup_routes(app):
    app.router.add_get('/', index)


if __name__ == '__main__':
    app = web.Application()
    try:
        videofile = open('bytedump.txt', 'rb')
        app["byteload"] = videofile.read()
    except Exception as e:
        print(e)
    setup_routes(app)
    web.run_app(app, host='0.0.0.0', port=9090)
