#!/bin/sh
# Public Domain
# Written by James Cameron <quozl@laptop.org> in 2017.
#
# usage: activity-translations ProjectName
#        where ProjectName is one listed on translate.sugarlabs.org
#

A=$1

# abandon if there is no activity metadata here
if [ ! -e activity/activity.info ]; then
    echo not an activity
    exit 2
fi

# abandon if there is no po file here
if [ ! -e po ]; then
    echo not internationalised
    exit 2
fi

# check for tools needed
if [ ! -e /usr/bin/pcregrep ]; then
    echo please install pcregrep
    exit 2
fi

if [ ! -e /usr/bin/wget ]; then
    echo please install wget
    exit 2
fi

if [ ! -e /usr/bin/unzip ]; then
    echo please install unzip
    exit 2
fi

# fetch latest translations
cd po
wget -q https://translate.sugarlabs.org/projects/$A/
for x in $(grep "/$A/translate/\"" index.html | \
	   cut -d/ -f2 | grep -v projects); do

    echo $x
    wget -q https://translate.sugarlabs.org/$x/$A/export/zip && \
        unzip -q -o zip && \
        rm -f zip
done
rm index.html

# remove empty translations
rm -v $(find . -type f -name '*.po' -not -execdir pcregrep -qM '^msgstr[^:]* "([^"]|"\n"(?!Project-Id-Version:))' '{}' ';' -print | sort)


# your next steps;
#
# review and commit the changes,
# run setup.py genpot, review, and commit the changes
#
# please discard trivial changes, to avoid git commit noise

