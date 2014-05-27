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

CLIENT = MongoClient('localhost', 27017)
DB = CLIENT.proxy

def timestamp():
    return datetime.datetime.now()

class Cache():

    def __init__(self,max_size=20):
        self.table = DB.cache
        self.max_size = max_size

    def insertResource(self,host,path,headers=None,body=None,size=None):
        try:
            #check cacheable
            #check if exists
            insert = {'host': host,'path': path,'headers':'','body':'','hits':0}
            if headers != None:
                insert['headers'] = headers
            if body != None:
                insert['body'] = body
            #get size len(body)
            #get items count from the html

            self.table.insert(insert)
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
                return result[0]
            else:
                #resource not found
                print('cache miss')
                return 0
        except Exception as e:
            print(e)

    def revalidateResource(self,host,path):
        #if cache-control is present -> validate max-age or expires
        #send conditional requests -> if-modified-since, if-none-match
        pass

    def replaceResource(self):
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
            '''
        rttM = RttMeasure()
        ping = rttM.getLastRTT('www.google.com')
        print(ping)
    except Exception as e:
        print(e)