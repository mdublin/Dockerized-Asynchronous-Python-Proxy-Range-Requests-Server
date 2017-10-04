**http-proxy with demo app server, both built using aiohttp and asyncio**

*note: this is not a complete proxy and test server, rather, this is just focused on range requests as a proof-of-principal for doing asynchronous byte streaming using the aiohttp HTTP client/server package for asyncio (PEP 3156).

To run, use Docker from inside parent directory:

```$ docker-compose up```


The proxy server is passing the range requests to the application server, and the application server is responding with the appropriate entity as per range requests, so proxy is not storing an entire response in a cache.


Usage statistics are available at ```http://localhost:8080/stats```

HEAD request to confirm server supports partial requests:

```$ curl -I http://localhost:8080/```

Response should look like:

```
HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8
Accept-Ranges: bytes
Content-Length: 98249008
Date: Sat, 22 Apr 2017 04:02:13 GMT
Server: Python/3.6 aiohttp/2.0.6
Via: MyProxyServer 1.0
```


A request with a single part range query param, for example:

```$ curl http://localhost:8080/?range=20-345```

Should return:

```
ftypiso5\x00\x00\x02\x00iso6mp41\x00\x00\x00\x08free\x02\x08\x1d\xdamdat\x00\x00\x03\x01\x06\x05\xff\xff\xfd\xdcE\xe9\xbd\xe6\xd9H\xb7\x96,\xd8 \xd9#\xee\xefx264 \x00\x80\x00\x00\x19#e\x88\x82\x00\t\x7f\xfe\xf7h\x9f\x02\x9b.\x1bi\xf3\xb8\xef\x7f\xd4"\x04\x85\xe7#\x11b\xef\xd9}\xf6Exx\xa4+\x18\x9eRi.\x9bx\xd3Qn\xf0\xe1\x10GR%
```


The response header for that same request via cURL:

```$ curl http://localhost:8080/?range=20-345 -I```

will be the following:

```
HTTP/1.1 206 Partial Content
Content-Type: application/octet-stream
Content-Range: bytes 20-345/98249008
Content-Length: 325
Date: Sat, 22 Apr 2017 07:13:59 GMT
Server: Python/3.6 aiohttp/2.0.6
Via: MyProxyServer 1.0
```


A request with a single part Range header, for example:

```$ curl http://localhost:8080/ -H "Range: bytes=20-345"```

will return:

```
ftypiso5\x00\x00\x02\x00iso6mp41\x00\x00\x00\x08free\x02\x08\x1d\xdamdat\x00\x00\x03\x01\x06\x05\xff\xff\xfd\xdcE\xe9\xbd\xe6\xd9H\xb7\x96,\xd8 \xd9#\xee\xefx264 \x00\x80\x00\x00\x19#e\x88\x82\x00\t\x7f\xfe\xf7h\x9f\x02\x9b.\x1bi\xf3\xb8\xef\x7f\xd4"\x04\x85\xe7#\x11b\xef\xd9}\xf6Exx\xa4+\x18\x9eRi.\x9bx\xd3Qn\xf0\xe1\x10GR%
```

The response header for that same request via cURL:

```$ curl http://localhost:8080/ -I -H "Range: bytes=90-2000"```

will be the following:

```
HTTP/1.1 206 Partial Content
Content-Type: application/octet-stream
Content-Range: bytes 20-345/98249008
Content-Length: 325
Date: Sat, 22 Apr 2017 07:13:59 GMT
Server: Python/3.6 aiohttp/2.0.6
Via: MyProxyServer 1.0
```


A multipart Range header request can also be made.

First, with header response info:

```$ curl http://localhost:8080/ -H "Range: bytes=10-20, 1-40"```

which will return:

```
HTTP/1.1 206 Partial Content
Content-Type: multipart/byteranges; boundary=3d6b6a416f9b5
Content-Length: 2416
Date: Sat, 22 Apr 2017 07:17:55 GMT
Server: Python/3.6 aiohttp/2.0.6
Via: MyProxyServer 1.0
```

A multipart request, like this:
```curl http://localhost:8080/ -H "Range: bytes=10-20, 1-40"```

will return this:

```
3d6b6a416f9b5
Content-Type: application/octet-stream
Content-Range: bytes 10-20, 1-40/98249008
00\x00\x18
3d6b6a416f9b5
Content-Type: application/octet-stream
Content-Range: bytes 10-20, 1-40/98249008
\x00\x00\x00\x18ftypiso5\x00\x00\x02%
```



An HTTP 416 response is provide if both range header and query parameter values are present but incongruent:

For example:
```$ curl http://localhost:8080/?range=100-500 -I -H "Range: bytes=90-2000"```

will return:
```
HTTP/1.1 416 Range Not Satisfiable
Content-Range: */
Via: MyProxyServer 1.0
Content-Length: 0
Content-Type: application/octet-stream
Date: Sat, 22 Apr 2017 04:38:45 GMT
Server: Python/3.6 aiohttp/2.0.6
```