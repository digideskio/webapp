import json
import logging
import re
import random
from datetime import datetime
from google.appengine.api import search

# TODO: Pool search api puts?

DO_NOT_FULL_TEXT = ['eventremarks', 'geologicalcontextid', 'scientificnameid', 
'nameaccordingtoid', 'month', 'decimallongitude', 'fieldnotes', 
'georeferenceddate', 'references', 'startdayofyear', 'minimumelevationinmeters', 
'taxonrank', 'identificationreferences', 'footprintspatialfit', 
'highergeographyid', 'accessrights', 'locationid', 'maximumelevationinmeters', 
'maximumdistanceabovesurfaceinmeters', 'type', 'taxonconceptid', 'eventid', 
'eventtime', 'identificationid', 'verbatimeventdate', 'verbatimdepth', 
'footprintwkt', 'verbatimcoordinatesystem', 'verbatimsrs', 'parentnameusageid', 
'scientificnameauthorship', 'minimumdepthinmeters', 'georeferenceremarks', 
'nameaccordingto', 'day', 'identificationverificationstatus', 'occurrenceid', 
'rights', 'footprintsrs', 'georeferenceverificationstatus', 'modified', 
'verbatimlatitude', 'associatedmedia', 'originalnameusageid', 
'datageneralizations', 'taxonomicstatus', 'taxonremarks', 
'coordinateuncertaintyinmeters', 'eventdate', 'namepublishedinyear', 
'individualcount', 'verbatimelevation', 'bibliographiccitation', 
'namepublishedinid', 'namepublishedin', 'dateidentified', 'verbatimtaxonrank', 
'locationaccordingto', 'acceptednameusage', 'minimumdistanceabovesurfaceinmeters', 
'informationwithheld', 'parentnameusage', 'occurrencedetails', 'description', 
'collectionid', 'acceptednameusageid', 'verbatimlongitude', 'individualid', 
'coordinateprecision', 'taxonid', 'maximumdepthinmeters', 'disposition', 
'vernacularname', 'decimallatitude', 'pointradiusspatialfit', 'language', 
'institutionid', 'rightsholder', 'verbatimcoordinates', 'originalnameusage', 
'nomenclaturalcode', 'associatedtaxa', 'nomenclaturalstatus', 'datasetid', 
'enddayofyear', 'url', 'emlrights', 'keyname', 'datasource_and_rights', 'citation',
'url']

def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False    
 
def valid_latlng(lat,lng):
    # accepts lat and lng as strings.
    if not is_number(lat):
        return False
    if not is_number(lng):
        return False
    flat = float(lat)
    if flat < -90 or flat > 90:
        return False
    flng = float(lng)
    if flng < -180 or flng > 180:
        return False
    return True
 
def valid_georef(rec):
    if rec.has_key('decimallatitude'):
        if rec.has_key('decimallongitude'):
            return valid_latlng(rec['decimallatitude'],rec['decimallongitude'])
    return False
 
def valid_binomial(rec):
    if rec.has_key('genus'):
      if rec.has_key('specificepithet'):
        # Sufficient condition for now to have these DwC terms populated.
        # Later may want to test them against a name authority to determine validity.
        return True
    return False
 
def rank(rec):
    rank = 0
    if valid_georef(rec) is True and valid_binomial(rec) is True:
        rank = 5
        if rec.has_key('year'):
            rank = 6
            if rec.has_key('month'):
                rank = 7
                if rec.has_key('day'):
                    rank = 8
    elif valid_binomial(rec) is True:
        rank = 1
        if rec.has_key('year'):
            rank = 2
            if rec.has_key('month'):
                rank = 3
                if rec.has_key('day'):
                    rank = 4
    return rank

def has_media(rec):
    if rec.has_key('associatedmedia'):
        return 1
    if rec.has_key('type'):
        if rec['type'].lower()=='sound':
            return 1
        if 'image' in rec['type'].lower():
            return 1
        return 0
    if rec.has_key('basisofrecord'):
        if rec['basisofrecord'].lower()=='machineobservation':
            return 1
    return 0

tissuetokens = ["+t", "tiss", "blood", "dmso", "dna", "extract", "froze", 
                "forzen", "freez", "heart", "muscle", "higado", "kidney",
                "liver", "lung", "nitrogen", "pectoral", "rinon",
                "kidney", "rnalater", "sample", "sangre", "toe", "spleen"]

def has_tissue(rec):
    if rec.has_key('preparations'):
        for token in tissuetokens:
            if token in rec['preparations'].lower():
                return 1
    return 0

def network(rec, network):
    if rec.has_key('network'):
        if network in rec['networks'].split(','):
            return 1
    return 0

def _corpus(recjson):
    vals = [val for key, val in recjson.iteritems() if key not in DO_NOT_FULL_TEXT]
    return reduce(lambda x,y: '%s %s' % (x, y), vals)

def _location(lat, lon):
    try:
        location = apply(search.GeoPoint, map(float, [lat, lon]))
    except:
        location = None
    return location

def _eventdate(year):
    try:
        eventdate = datetime.strptime(year, '%Y')
    except:
        eventdate = None
    return eventdate

def build_search_index(entity):
    data = json.loads(entity.record)
    year, genus, icode, country, specep, lat, lon, catnum = map(data.get, 
        ['year', 'genus', 'institutioncode', 'country', 'specificepithet', 
        'decimallatitude', 'decimallongitude', 'catalognumber'])

    doc = search.Document(
        doc_id=data['keyname'],
        rank=rank(data),
		fields=[search.TextField(name='year', value=year),
				search.TextField(name='genus', value=genus),
        		search.TextField(name='institutioncode', value=icode),
                search.TextField(name='country', value=country),            
                search.TextField(name='specificepithet', value=specep),
                search.TextField(name='catalognumber', value=catnum),
                search.NumberField(name='media', value=has_media(data)),            
                search.NumberField(name='tissue', value=has_tissue(data)),            
                search.NumberField(name='manis', value=network(data, 'manis')),            
                search.NumberField(name='ornis', value=network(data, 'ornis')),            
                search.NumberField(name='herpnet', value=network(data, 'herpnet')),            
                search.NumberField(name='fishnet', value=network(data, 'fishnet')),            
                search.NumberField(name='rank', value=rank(data)),            
        		search.TextField(name='record', value=entity.record)])

    location = _location(lat, lon)
    eventdate = _eventdate(year)

    if location:
        doc.fields.append(search.GeoField(name='location', value=location))
        doc.fields.append(search.NumberField(name='mappable', value=1))
    else:
        doc.fields.append(search.NumberField(name='mappable', value=0))

    if eventdate:
        doc.fields.append(search.DateField(name='eventdate', value=eventdate))
	
	try:
	    search.Index(name='dwc_search').put(doc)
	    entity.indexed = True
	    entity.put()
	except search.Error:
	    logging.exception('Put failed for doc %s' % doc.doc_id)
