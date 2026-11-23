"""Unit tests for snapshots.py with rows shaped like the live OpenAPI answers (no network)."""

import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cache import Fetcher, NoDataError  # noqa: E402
from snapshots import SnapshotMissing, parse_pipeline, parse_statuses, snapshot, tw_date, tw_range  # noqa: E402

APPLY_KEYS = ["Code", "Company", "ApplicationDate", "Chairman", "AmountofCapital ", "CommitteeDate", "ApprovedDate",
              "AgreementDate", "ListingDate", "ApprovedListingDate", "Underwriter", "UnderwritingPrice", "Note"]


def cmode_row(code, **flags):
    row = {"Date": "1151123", "SecuritiesCompanyCode": code, "CompanyName": "n", "AlteredTrading": "",
           "PeriodicTrading": "", "ManagedStock": "", "MatchingFrequency": "", "SuspensionOfTrading": "",
           " FinancialAnnouncements": ""}
    row.update(flags)
    return row


class Dates(unittest.TestCase):
    def test_tw_dates(self):
        self.assertEqual([tw_date(x) for x in ("1151120", "115/11/18", "20261029", "")],
                         ["2026-11-20", "2026-11-18", "2026-10-29", None])
        self.assertEqual(tw_range("115/11/23～115/11/27"), ("2026-11-23", "2026-11-27"))
        self.assertEqual(tw_range("1151120~1151126"), ("2026-11-20", "2026-11-26"))

    def test_unreadable_dates_give_none(self):
        self.assertEqual([tw_date(x) for x in ("尚未公告", "1151340", None)], [None, None, None])


class Statuses(unittest.TestCase):
    def test_halt_applies_only_while_halted(self):
        p = {"TWTAWU": [{"Code": "2314", "TradingHaltDate": "1151110", "TradingResumptionDate": "1151111"}]}
        self.assertIn("suspended", parse_statuses("2026-11-10", p)["2314"])
        self.assertNotIn("2314", parse_statuses("2026-11-20", p))

    def test_halt_ends_on_resumption_date(self):
        p = {"TWTAWU": [{"Code": "2314", "TradingHaltDate": "1151110", "TradingResumptionDate": "1151111"}]}
        self.assertEqual(parse_statuses("2026-11-11", p), {})

    def test_disposition_in_force_on_its_last_day(self):
        p = {"punish": [{"Code": "3008", "DispositionPeriod": "115/11/16～115/11/20"}]}
        self.assertEqual(parse_statuses("2026-11-20", p), {"3008": {"disposition"}})

    def test_cmode_fullwidth_flags(self):
        row = {"SecuritiesCompanyCode": "2067", "AlteredTrading": "Ｙ", "PeriodicTrading": "", "ManagedStock": "",
               "MatchingFrequency": "", "SuspensionOfTrading": ""}
        self.assertEqual(parse_statuses("2026-11-20", {"cmode": [row]})["2067"], {"altered_trading"})

    def test_cmode_managed_suspended_periodic(self):
        p = {"cmode": [cmode_row("1111", ManagedStock="Ｙ", SuspensionOfTrading="Ｙ"),
                       cmode_row("2222", MatchingFrequency="Ｙ"), cmode_row("3333", PeriodicTrading="Ｙ")]}
        self.assertEqual(parse_statuses("2026-11-20", p), {"1111": {"managed", "suspended"},
                                                           "2222": {"periodic_auction"},
                                                           "3333": {"periodic_auction"}})

    def test_notice_placeholder_ignored(self):
        self.assertEqual(parse_statuses("2026-11-20", {"notice": [{"Number": "0", "Code": "", "Name": ""}]}), {})

    def test_disposition_by_period_end_and_attention_lists(self):
        p = {"punish": [{"Code": "1569", "DispositionPeriod": "115/11/23～115/11/27"},
                        {"Code": "2002", "DispositionPeriod": "115/11/10～115/11/16"}],
             "disposal": [{"SecuritiesCompanyCode": "6488", "DispositionPeriod": "1151120~1151126"}],
             "notice": [{"Number": "1", "Code": "2330", "Name": "台積電"}],
             "warning": [{"Date": "1151120", "SecuritiesCompanyCode": "8299", "CompanyName": "群聯"}],
             "TWT85U": [{"Code": "1213", "Name": "大飲", "PeriodicCallAuctionTrading": "  "}]}
        self.assertEqual(parse_statuses("2026-11-20", p), {"1569": {"disposition"}, "6488": {"disposition"},
                                                           "2330": {"attention"}, "8299": {"attention"},
                                                           "1213": {"altered_trading"}})

    def test_unreadable_date_counts_as_in_force(self):
        p = {"punish": [{"Code": "1569", "DispositionPeriod": ""}],
             "TWTAWU": [{"Code": "2314", "TradingHaltDate": "", "TradingResumptionDate": ""}]}
        self.assertEqual(parse_statuses("2026-11-20", p), {"1569": {"disposition"}, "2314": {"suspended"}})

    def test_cash_offering_both_boards(self):
        p = {"TWT48U_ALL": [{"Date": "1151127", "Code": "3706", "SubscriptionRatio": "0.08219551", "SubscriptionPricePerShare": "52.0000"},
                            {"Date": "1151202", "Code": "00406A", "SubscriptionRatio": "", "SubscriptionPricePerShare": ""},
                            {"Date": "1151110", "Code": "2345", "SubscriptionRatio": "0.01782156", "SubscriptionPricePerShare": "尚未公告"}],
             "exright": [{"ExRrightsExDividendDate": "1151203", "SecuritiesCompanyCode": "6160",
                          "SubscriptionRatioToNewSharesIssued": "0.16060945", "SubscriptionPricePerShare": "註4"},
                         {"ExRrightsExDividendDate": "1151203", "SecuritiesCompanyCode": "5483",
                          "SubscriptionRatioToNewSharesIssued": "0.00000000", "SubscriptionPricePerShare": "0.00"}]}
        self.assertEqual(parse_statuses("2026-11-20", p), {"3706": {"cash_offering"}, "6160": {"cash_offering"}})


class Pipeline(unittest.TestCase):
    def test_applylisting_by_position(self):
        row = dict(zip(APPLY_KEYS, ["12", "7867", "特力屋", "1150429", "x", "960000", "1150609", "1150721", "1150730",
                                    "1151030", "x", "44.06", ""]))
        up = parse_pipeline("2026-10-20", {"applylistingLocal": [row]})["upcoming"]
        self.assertEqual((up[0]["code"], up[0]["listing_date"], up[0]["price"]), ("7867", "2026-10-30", 44.06))
        self.assertEqual(parse_pipeline("2026-11-20", {"applylistingLocal": [row]})["upcoming"], [])

    def test_tpex_applicants_within_365_days(self):
        def applicant(code, applied):
            return {"Date": applied, "SecuritiesCompanyCode": code, "CompanyName": "n", "ListingDate": "",
                    "OfferingPrice": ""}

        up = parse_pipeline("2026-11-20", {"applicants": [applicant("7863", "20261029"),
                                                          applicant("6999", "20251119")]})["upcoming"]
        self.assertEqual(up, [{"code": "7863", "name": "n", "market": "tpex", "applied": "2026-10-29",
                               "listing_date": None, "price": None}])

    def test_first_five_emerging_and_delisted(self):
        trade = {"SecurCode": "7867", "SecurName": "特力屋", "1stTradingDate": "1151030", "5thTradingDate": "1151105",
                 "PriceUnderwritten": "44.06", "Code": "11", "BuySell": "B"}
        p = {"TWT88U": [trade, dict(trade, Code="12", BuySell="S")],
             "ipo_no_limit": [{"SecuritiesCompanyCode": "7848", "StartDateForStabilizationOperation": "1151116",
                               "EndDateForStabilizationOperation": "1151120", "UnderwritingPrice": "249.65"}],
             "esb_quotes": [{"SecuritiesCompanyCode": "1260", "Average": "29.09", "LatestPrice": "30",
                             "TransactionVolume": "18881", "ApplyingStatus": ""}],
             "suspendListing": [{"DelistingDate": "099/01/05", "Company": "a", "Code": "2432"},
                                {"DelistingDate": "115/11/18", "Company": "b", "Code": "1589"},
                                {"DelistingDate": "105/06/30", "Company": "c", "Code": "2432"}]}
        out = parse_pipeline("2026-11-20", p)
        self.assertEqual(out["first_five"], {"7867": {"first": "2026-10-30", "fifth": "2026-11-05", "price": 44.06},
                                             "7848": {"first": "2026-11-16", "fifth": "2026-11-20", "price": 249.65}})
        self.assertEqual(out["emerging"], {"1260": {"avg": 29.09, "last": 30.0, "volume": 18881.0,
                                                    "applying_status": ""}})
        self.assertEqual(out["delisted"], {"2432": "2016-06-30", "1589": "2026-11-18"})


class Snapshot(unittest.TestCase):
    def fetcher(self, bodies):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.requested = []

        def opener(request, timeout):
            self.requested.append(request.full_url)
            return io.BytesIO(bodies[request.full_url.rsplit("/", 1)[1]])

        return Fetcher(root=tmp.name, pause_s=0, opener=opener, sleep=lambda s: None)

    def test_snapshot_missing_for_past_asof(self):
        f = self.fetcher({})
        with self.assertRaises(SnapshotMissing):
            snapshot(f, "TWT85U", "2026-11-13", live=False)
        self.assertEqual(self.requested, [])

    def test_snapshot_cached_under_asof(self):
        f = self.fetcher({"notice": b"[]", "tpex_cmode": b'{"message": "busy"}'})
        self.assertEqual(snapshot(f, "notice", "2026-11-20", live=True), [])        # an empty list is valid
        self.assertEqual(snapshot(f, "notice", "2026-11-20", live=False), [])       # served from the cache
        self.assertEqual(self.requested, ["https://openapi.twse.com.tw/v1/announcement/notice"])
        with self.assertRaises(NoDataError):
            snapshot(f, "cmode", "2026-11-20", live=True)                           # an object is not a snapshot


if __name__ == "__main__":
    unittest.main()
