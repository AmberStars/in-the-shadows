import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
import park_data

class DataTests(unittest.TestCase):
    def test_actual_photos_and_coordinates(self):
        o=park_data.compact_observation({'id':7,'geojson':{'coordinates':[-84.76,43.59]},'taxon':{'id':1,'name':'Animalia','default_photo':{'url':'WRONG'}},'photos':[{'url':'https://example.org/photos/2/square.jpg','attribution':'Observer credit'}]})
        self.assertEqual(o['photos'][0]['url'],'https://example.org/photos/2/medium.jpg')
        self.assertEqual(o['photos'][0]['credit'],'Observer credit')
        self.assertEqual(o['coordinates'],[-84.76,43.59])
        self.assertIsNone(park_data.compact_observation({'id':8}))

    def test_pagination_and_cache_resume(self):
        def record(i):
            return {'id':i,'geojson':{'coordinates':[-84.76,43.59]}}
        first=MagicMock(); first.json.return_value={'total_results':201,'results':[record(i) for i in range(1,201)]}
        last=MagicMock(); last.json.return_value={'total_results':1,'results':[record(201)]}
        session=MagicMock();session.get.side_effect=[first,last]
        with tempfile.TemporaryDirectory() as directory, patch.object(park_data,'CACHE',Path(directory)), patch.object(park_data.requests,'Session',return_value=session), patch.object(park_data.time,'sleep'):
            result=park_data.fetch_observations()
            self.assertEqual(len(result),201)
            self.assertEqual(session.get.call_args_list[1].kwargs['params']['id_above'],200)
            session.get.reset_mock()
            self.assertEqual(len(park_data.fetch_observations()),201)
            session.get.assert_not_called()

if __name__ == '__main__': unittest.main()
