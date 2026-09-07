import io

from django.test import SimpleTestCase

from core.ovkml_converter import parse_kml_or_kmz
from core.views import _convert_dxf_bytes_to_kml


class DxfCoordinateConversionTests(SimpleTestCase):
    def test_projected_dxf_coordinates_are_converted_to_wgs84(self):
        import ezdxf

        document = ezdxf.new('R2010')
        document.modelspace().add_point((500000, 4700000), dxfattribs={'layer': 'TEST'})
        output = io.StringIO()
        document.write(output)

        kml_bytes, stats = _convert_dxf_bytes_to_kml(output.getvalue().encode(), 'sample')
        records, file_format = parse_kml_or_kmz(
            kml_bytes,
            input_crs='cgcs2000_proj',
            output_crs='wgs84',
            central_meridian=90,
        )

        self.assertEqual(file_format, 'kml')
        self.assertEqual(stats['point_count'], 1)
        self.assertEqual(len(records), 1)
        self.assertAlmostEqual(records[0].target_lon, 90, places=5)
        self.assertAlmostEqual(records[0].target_lat, 42.4354, places=3)