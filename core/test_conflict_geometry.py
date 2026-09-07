from django.test import SimpleTestCase

from core.views import _analyze_conflicts


class HeritageRangeConflictTests(SimpleTestCase):
    site = {
        'id': 1,
        'name': '测试文物',
        'level': 'GB',
        'longitude': 5.0,
        'latitude': 5.0,
        'boundary_rings': [[(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0), (0.0, 0.0)]],
        'bbox': (0.0, 0.0, 10.0, 10.0),
    }

    def test_point_inside_heritage_range_conflicts(self):
        conflicts = _analyze_conflicts(
            [{'name': '点', 'geometry_type': 'Point', 'coordinates': (5.0, 5.0), 'source': 'point.kml'}],
            threshold_m=1,
            site_points=[self.site],
        )

        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]['relation'], '点位于文物本体边界内')
        self.assertEqual(conflicts[0]['distance_m'], 0.0)

    def test_line_crossing_range_with_endpoints_outside_conflicts(self):
        conflicts = _analyze_conflicts(
            [{
                'name': '穿越线',
                'geometry_type': 'LineString',
                'coordinates': [(-1.0, 5.0), (11.0, 5.0)],
                'source': 'line.kml',
            }],
            threshold_m=1,
            site_points=[self.site],
        )

        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]['relation'], '线与文物本体范围相交')
        self.assertEqual(conflicts[0]['distance_m'], 0.0)

    def test_polygon_crossing_range_without_contained_vertices_conflicts(self):
        conflicts = _analyze_conflicts(
            [{
                'name': '穿越面',
                'geometry_type': 'Polygon',
                'coordinates': [[(-1.0, 4.0), (11.0, 4.0), (11.0, 6.0), (-1.0, 6.0), (-1.0, 4.0)]],
                'source': 'polygon.kml',
            }],
            threshold_m=1,
            site_points=[self.site],
        )

        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]['relation'], '面与文物本体范围相交')
        self.assertEqual(conflicts[0]['distance_m'], 0.0)