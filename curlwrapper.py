import os
import xmlrpclib
import urllib
import pycurl
from cStringIO import StringIO

import logger

# a pycurl-based replacement for the previous version that relied on forking curl

def retrieve(url, cacert=None, postdata=None, timeout=90):
    curl= pycurl.Curl()
    curl.setopt(pycurl.URL,url)

    # reproduce --fail from the previous version
    curl.setopt(pycurl.FAILONERROR,1)
    # don't want curl sending any signals
    curl.setopt(pycurl.NOSIGNAL, 1)

    # do not follow location when attempting to download a file
    # curl.setopt(pycurl.FOLLOWLOCATION, 0)

    # store result on the fly 
    buffer=StringIO()
    curl.setopt(pycurl.WRITEFUNCTION,buffer.write)
           
    # set timeout
    if timeout: 
        curl.setopt(pycurl.CONNECTTIMEOUT, timeout)
        curl.setopt(pycurl.TIMEOUT, timeout)

    # set cacert
    if cacert: 
        curl.setopt(pycurl.CAINFO, cacert)
        curl.setopt(pycurl.SSL_VERIFYPEER, 2)
    else:
        curl.setopt(pycurl.SSL_VERIFYPEER, 0)

    # set postdata
    if postdata:
        if isinstance(postdata,dict):
            postfields = urllib.urlencode(postdata)
        else:
	    postfields=postdata
        curl.setopt(pycurl.POSTFIELDS, postfields)

    # go
    try:
        curl.perform()

        errcode = curl.getinfo(pycurl.HTTP_CODE)
        curl.close()

        # check the code, return 1 if successfull
	if errcode == 60:
	    raise xmlrpclib.ProtocolError (url,errcode, "SSL certificate validation failed", postdata)
        elif errcode != 200:
            raise xmlrpclib.ProtocolError (url,errcode, "http error %d"%errcode, postdata)

    except pycurl.error, err:
        errno, errstr = err
        raise xmlrpclib.ProtocolError(url, errno, "curl error %d: '%s'\n" %(errno,errstr),postdata )

    return buffer.getvalue()
