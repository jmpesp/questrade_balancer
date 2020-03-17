# Questrade automatic balancer #

When run against a Questrade portfolio, this tool shows purchase and sell orders
necessary to bring the portfolio back to the given allocation percentages.

Create a portfolio.json in this directory. Example:

    {
        "symbols": {
            "VSB.TO": {
                "percent": 0.5
            },
            "XIU.TO": {
                "percent": 0.5
            }
        }
    }

"percent" here is a fraction of 1. Put as many symbols in here as you like, but
the cumulative "percent" can only be 1. The total percent can be less than 1
(100%), the rest will be kept as cash.

Obtain an app token from Questrade, and place it in a file in this directory
called "token". When balance.py is run it will refresh this token and write the
result out to that same file. Note that this token expires and if it does you
will need to manually generate a new one.

An example output:

    XIU.TO at 19.54
    value: target 15094.561675 actual 14826.38
    value difference: -268.181675
    could buy 13

# DISCLAIMER #

Use at your own risk! This tool only makes suggestions, it does not buy or sell.
You are responsible for what you do with that information.

