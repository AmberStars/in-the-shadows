import unittest
from shapely.geometry import Polygon, MultiPolygon, Point
from park_data import GEOD, park_circle, in_circle

class ParkCircleTests(unittest.TestCase):
    def test_farthest_vertex_includes_all_islands(self):
        first = Polygon([(-84.77,43.59),(-84.76,43.59),(-84.76,43.60),(-84.77,43.60)])
        island = Polygon([(-84.74,43.59),(-84.73,43.59),(-84.73,43.60),(-84.74,43.60)])
        center,radius = park_circle(MultiPolygon([first,island]))
        self.assertGreater(radius,1500)
        for poly in [first,island]:
            for xy in poly.exterior.coords:
                self.assertTrue(in_circle(center,radius,xy))
        self.assertFalse(in_circle(center,radius,[-85,44]))

    def test_circle_includes_points_outside_polygon_as_requested(self):
        poly=Polygon([(-84.77,43.59),(-84.76,43.59),(-84.76,43.60),(-84.77,43.60)])
        center,radius=park_circle(poly)
        lng,lat,_=GEOD.fwd(center[1],center[0],90,radius*.95)
        self.assertFalse(poly.covers(Point(lng,lat)))
        self.assertTrue(in_circle(center,radius,[lng,lat]))
        lng,lat,_=GEOD.fwd(center[1],center[0],90,radius+10)
        self.assertFalse(in_circle(center,radius,[lng,lat]))

    def test_point_has_no_invented_radius(self):
        center,radius=park_circle(Point(-84.76,43.59))
        self.assertAlmostEqual(radius,0)
        self.assertAlmostEqual(center[0],43.59)

if __name__ == '__main__': unittest.main()
