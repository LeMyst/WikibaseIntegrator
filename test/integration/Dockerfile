# The Wikibase Suite image with the WikibaseLexeme extension, which it doesn't bundle.
#
# The image loads every file of /var/www/html/LocalSettings.d/, and its entrypoint runs update.php after the install
# and on every boot, which creates the tables of the extension.
FROM wikibase/wikibase:7

# The release branch of the MediaWiki version of the image (MediaWiki 1.45)
ARG WIKIBASE_LEXEME_BRANCH=REL1_45

ADD https://github.com/wikimedia/mediawiki-extensions-WikibaseLexeme.git#${WIKIBASE_LEXEME_BRANCH} /var/www/html/extensions/WikibaseLexeme
COPY LocalSettings.d/ /var/www/html/LocalSettings.d/
