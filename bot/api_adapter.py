# encoding: utf-8

"""Yahoo API Adapter"""

import logging, requests, urllib.parse
import xml.etree.ElementTree as ET

logger = logging.getLogger('chat-bot')


class ApiException(Exception):

    def __init__(self, message, code=None):
        self.message = message
        self.code = code

    def __str__(self):
        return self.message


class YahooFinanceApiAdapter(object):
    """Yahoo Finance API Adapter"""

    BOT_STOCK_URL = 'http://finance.yahoo.com/webservice/v1/symbols/{0}/quote'

    BOT_RANGE_URL = ('http://query.yahooapis.com/v1/public/yql?q=select%20*%20from%20yahoo.finance'
                     '.quotes%20where%20symbol%20in%20({0})&env=store://datatables.org/alltableswithkeys')

    # Samsung Galaxy S6
    BOT_USER_AGENT_STR = ('Mozilla/5.0 (Linux; Android 6.0.1; SM-G920V Build/MMB29K) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/52.0.2743.98 Mobile Safari/537.36')

    def query_stock(self, company_code):
        try:
            api_response = requests.get(self.BOT_STOCK_URL.format(urllib.parse.quote(company_code)),
                                        headers={'User-Agent': self.BOT_USER_AGENT_STR})
            api_response.raise_for_status()
            doc = ET.ElementTree(ET.fromstring(api_response.text))

            resource = doc.findall('.//resource')

            if not resource:
                # If not resources returned, it means there is no information for the given company.
                raise ApiException('Could not find information for company {0}'.format(company_code))

            msg_pattern = "{0} ({1}) quote is ${2} per share."

            element = resource[0]
            name_fld = element.findall('field[@name="name"]')
            price_fld = element.findall('field[@name="price"]')

            if not name_fld or not price_fld:
                raise ApiException('Stock API returned answer without name or price fields.', code='BOT04')

            return {'companyCode': company_code, 'name': name_fld[0].text, 'price': float(price_fld[0].text),
                    'message': msg_pattern.format(company_code, name_fld[0].text, price_fld[0].text),
                    'error': False, 'lang': 'en'}
        except Exception as e:
            msg = 'Error when querying Stock API for company {0}.'.format(company_code)
            raise ApiException(msg, code='BOT03') from e

    def query_day_range(self, args):
        """This method queries the  Yahoo! Finance API to get stock ranges.
        :param args: Company code to query, or a list of company codes.
        """
        if not args:
            raise ApiException('Company code not provided.', code='BOT01')

        if isinstance(args, (list, tuple)):
            query_codes = ','.join(['"{0}"'.format(code) for code in args])
        else:
            query_codes = '"{0}"'.format(args)

        try:
            api_response = requests.get(self.BOT_RANGE_URL.format(urllib.parse.quote(query_codes)))
            api_response.raise_for_status()
            doc = ET.ElementTree(ET.fromstring(api_response.text))

            quotes = doc.findall('.//quote')

            if not quotes:
                logger.error('Unexpected response from Yahoo Ranges API', api_response.text)
                raise ApiException('Unexpected response from Yahoo Ranges API')

            # This API always returns a result, even when the code is incorrect. We can check if the
            # company code is valid by inspecting certain fields in the answer. If they are empty,
            # we assume there is no information associated with the company ID given.
            msg_pattern = '{0} ({1}) Days Low quote is ${2} and Days High is ${3}.'
            results = []

            for quote in quotes:
                try:
                    comp_name = quote.find('Name').text
                    days_low = quote.find('DaysLow').text
                    days_high = quote.find('DaysHigh').text
                    code = quote.attrib['symbol']

                    if not (comp_name and days_low and days_high and code):
                        logger.error('Error getting information from Yahoo Finance Ranges API: '
                                     + repr((code, comp_name, days_low, days_high)))
                        results.append({'error': True, 'message': 'Could not find information '
                                                                  'for company {0}'.format(code)})
                        continue

                    results.append({'companyCode': code, 'name': comp_name, 'error': False, 'lang': 'en',
                                    'daysLow': float(days_low), 'daysHigh': float(days_high),
                                    'message': msg_pattern.format(code, comp_name, days_low, days_high)})
                except (IndexError, TypeError, ValueError, AttributeError) as e:
                    logger.error('Error getting data for company {0}'.format(
                        quote.attrib.get('symbol', '""')))
                    logger.exception(e)
                    results.append({'error': True, 'message': 'Error getting data for company {0}'
                                   .format(quote.attrib['symbol'])})

            return {'error': False, 'results': results}

        except Exception as e:
            msg = 'Error getting data from Yahoo Finance Ranges API for company {0}.'.format(query_codes)
            raise ApiException(msg, code='BOT03') from e
