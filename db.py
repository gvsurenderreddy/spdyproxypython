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

CLIENT = MongoClient('localhost', 27017)
DB = CLIENT.proxy

class baseDB():
    def __init__(self,db):
        self.db = client[db]
    def insert(self,obj):
        result = self.db.insert(obj)
        if result:
            return result
        return 0

class Cache():

    def __init__(self):
        self.table = DB.cache

    def insertResource(self,host,path,headers=None,body=None,size=None):
        try:
            #check cacheable
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
        try:
            result = self.table.find_one({'host':host, 'path':path})
            if result.count() != 0:
                #check freshness
                #revalidate resource
                #return resource
                pass
            else:
                #resource not found
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

    def saveRTT(self,host,time,timestamp):
        try:
            insert = {"host": host,"ping": ping,"timestamp":timestamp}
            self.table.insert(insert)
        except Exception as e:
            print(e)

    def getLastRTT(self,host):
        try:
            result = self.table.find_one({'host':host}).sort('timestamp')
            if result.count() != 0:
                return result[result.count()-1]['ping']
            else:
                return self.findRTT(host)
        except Exception as e:
            print(e)

    def findRTT(self,host):
        return 0

if __name__ == "__main__":
    try:
        client = MongoClient('localhost', 27017)
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
    except Exception as e:
        print(e)