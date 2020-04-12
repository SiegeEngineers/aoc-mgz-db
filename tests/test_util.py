import datetime
import unittest

from mgzdb import util


class TestUtil(unittest.TestCase):

    def test_parse_filename(self):
        self.assertEqual(
            util.parse_filename('MP Replay v101.101.34793.0 @2020.02.13 213505 (1).aoe2record'),
            (datetime.datetime(2020, 2, 13, 21, 35, 5), '101.101.34793.0')
        )

        self.assertEqual(
            util.parse_filename('rec.20190615-112706-anything.mgz'),
            (datetime.datetime(2019, 6, 15, 11, 27, 6), None)
        )

        self.assertEqual(
            util.parse_filename('recorded game -  29-Mar-2001 00`35`51 3v3 iketh vs woogy.mgx'),
            (datetime.datetime(2001, 3, 29, 0, 35, 51), None)
        )

        self.assertEqual(
            util.parse_filename('partida-grabada-21-sep-2010-22-19-44.mgx'),
            (datetime.datetime(2010, 9, 21, 22, 19, 44), None)
        )

    def test_parse_series_path(self):
        self.assertEqual(
            util.parse_series_path('987654321-A vs B.zip'),
            ('A vs B', '987654321')
        )

        self.assertEqual(
            util.parse_series_path('norway-brazil-2v2_showmatch-20160902-1-1000-Viper-Mbl vs Fire-Dogao.zip'),
            ('Viper Mbl vs Fire Dogao', 'norway-brazil-2v2_showmatch-20160902-1-1000')
        )

        self.assertEqual(
            util.parse_series_path('tyrant_war_1-201403-1-1000-TyRanT War Day 1-2.zip'),
            ('TyRanT War Day 1 2', 'tyrant_war_1-201403-1-1000')
        )
