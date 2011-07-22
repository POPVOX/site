#!/bin/sh

mkdir -p popvox/fixtures
./manage dumpdata --format=json adserver.Format adserver.Target adserver.TargetGroup adserver.Advertiser adserver.Order adserver.Banner > popvox/fixtures/test_adserver.json
./manage dumpdata --format=json popvox.IssueArea popvox.MemberOfCongress popvox.CongressionalCommittee > popvox/fixtures/test_pvgeneral.json
