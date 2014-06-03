#rtt measure
#host,ping,timestamp

#bw measure
#constant, or speedtest_cli

#cache
#host, path, headers, body, initial_timestamp, revalidation_timestamp, hits, size, items_count

#item count .count()
#last item index .count()-1
#.sort() asc

from pymongo import MongoClient
import datetime
import os
import socket
import re
import configparser
#from decodeChunked import decodeChunked
from SpdyConnection import SpdyConnection

CLIENT = MongoClient('localhost', 27017)
DB = CLIENT.proxy

def timestamp():
    return datetime.datetime.now()

class Cache():

    def __init__(self,max_size=20):
        self.table = DB.cache
        self.max_size = max_size

    def insertResource(self,host,path,header=None,body=None,size=None):
        try:
            #TODO check cacheable
            insert = {'host': host,'path': path,'header':'','body':'','hits':0,'items_count':0}
            if header != None:
                insert['header'] = header
            if body != None:
                insert['body'] = body
                if size is None:
                    insert['size'] = len(body)
                insert['items_count'] = self.countItems(body)
            #check if exists
            if self.searchResource(host,path) == 0:
                self.table.insert(insert)
            else:
                self.table.update({'host':host, 'path':path},insert)
        except Exception as e:
            print(e)

    def searchResource(self,host,path):
        print('searching... '+host+path)
        try:
            result = self.table.find({'host':host, 'path':path})
            if result.count() != 0:
                #check freshness
                #revalidate resource
                #return resource
                print('cache hit!')
                self.table.update({'host':host, 'path':path},{'$inc':{hits:1}})
                return result[0]
            else:
                #resource not found
                print('cache miss')
                return 0
        except Exception as e:
            print(e)

    def countItems(self,body):
        #count items of the html (src and css, excluding comments)
        try:
            uncommented = re.sub(r"<!--(.*?)-->",'', body.decode('UTF-8','ignore'))
            matchs = re.findall(r"src=|text/css", uncommented)
            return len(matchs)
        except:
            return 0

    def revalidateResource(self,host,path):
        #if cache-control is present -> validate max-age or expires
        #send conditional requests -> if-modified-since, if-none-match
        pass

    def replaceResource(self):
        pass

class DecisionTree():

    def __init__(self):
        config = configparser.ConfigParser()
        config.read('config.ini')
        self.constants = config['TREE CONSTANTS']

    def makeChoice(self,host,path=None):
        pass

class RttMeasure():

    def __init__(self):
        self.table = DB.rtt

    def saveRTT(self,host,ping,timestamp=timestamp()):
        try:
            insert = {"host": host,"ping": ping,"timestamp":timestamp}
            self.table.insert(insert)
        except Exception as e:
            print(e)

    def getLastRTT(self,host):
        try:
            result = DB.rtt.find({'host':host}).sort('timestamp')
            if result.count() != 0:
                return result[result.count()-1]['ping']
            else:
                rtt = self.findRTT(host)
                if rtt != 0:
                    self.saveRTT(host,rtt)
                return rtt
        except Exception as e:
            print(e)

    #return ping in ms    
    def findRTT(self,host):
        try:
            res = os.popen("ping -c 1 "+host).read()
            res = res.split('time=')
            res = res[1].split(' ms')
            return res[0]
        except:
            return 0

#host,http=0,https=0,spdy=0
class MethodGuesser():

    def __init__(self,max_size=20):
        self.table = DB.availableMethods

    def getMethod(self,host):
        result = self.table.find({'host':host})
        if result.count() != 0:
            return result[0]

    def guesser(self,host):
        guessing = {'host':host,'http':0,'https':0,'spdy':0}
        #trying http...
        try:
            soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            soc.connect((host,80))
            guessing['http'] = 1
            soc.close()
        except Exception as e:
            pass
        #trying https...
        try:
            soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            soc.settimeout(2)
            soc.connect((host,443))
            guessing['https'] = 1
            soc.close()
        except Exception as e:
            pass
        #trying spdy...
        try:
            spdyClient = SpdyConnection((host,443))
            spdyClient.close()
            guessing['spdy'] = 1
        except Exception as e:
            pass
        search = {'host':host}
        result = self.table.find(search)
        if result.count() != 0:
            self.table.update(search,guessing)
        else:
            print('insert available methods')
            self.table.insert(guessing)

if __name__ == "__main__":
    try:
        '''client = MongoClient('localhost', 27017)
        db = client.test #selecting database
        insert = {'ping':2,'host':'www.google.com'}
        db.tabla.insert(insert)
        insert = {'ping':42,'host':'www.google.com'}
        db.tabla.insert(insert)
        insert = {'ping':1,'host':'www.google.com'}
        db.tabla.insert(insert)
        people = db.tabla.find({'host':'www.google.com'}).sort('ping')
        #print(people.count())
        if people.count() != 0:
            print(people[people.count()-1]['ping'])
            
        rttM = RttMeasure()
        ping = rttM.getLastRTT('www.google.com')
        print(ping)
        '''
        guess = MethodGuesser()
        print(guess.getMethod('www.unlu.edu.ar'))
        print(guess.getMethod('www.google.com.ar'))
        print(guess.getMethod('www.asocmedicalujan.com.ar'))
    except Exception as e:
        print(e)