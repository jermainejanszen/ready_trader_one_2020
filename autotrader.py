import asyncio
import numpy as np
import statistics

from typing import List, Tuple

from ready_trader_one import BaseAutoTrader, Instrument, Lifespan, Side


class AutoTrader(BaseAutoTrader):

    # Limits
    activeOrderLimit = 10
    ordersPerSecondLimit = 20
    activeVolumeLimit = 200
    positionLimit = 100

    # Counters
    currentActiveOrders = 0

    # States
    bidPrice = 0
    askPrice = 0
    middlePrice = 0
    theoPrice = 0
    previousPrices = []
    priceMovingAverage = 0
    priceDirection = 0

    # Parameters
    desiredSpread = 

    def __init__(self, loop: asyncio.AbstractEventLoop):
        """Initialise a new instance of the AutoTrader class."""
        super(AutoTrader, self).__init__(loop)

    def on_error_message(self, client_order_id: int, error_message: bytes) -> None:
        """Called when the exchange detects an error.

        If the error pertains to a particular order, then the client_order_id
        will identify that order, otherwise the client_order_id will be zero.
        """
        pass

    def on_order_book_update_message(self, instrument: int, sequence_number: int, ask_prices: List[int],
                                     ask_volumes: List[int], bid_prices: List[int], bid_volumes: List[int]) -> None:
        """Called periodically to report the status of an order book.

        The sequence number can be used to detect missed or out-of-order
        messages. The five best available ask (i.e. sell) and bid (i.e. buy)
        prices are reported along with the volume available at each of those
        price levels.
        """

        if instrument == Instrument.Future:
            weightedAskPrices = []
            for i in range(len(ask_prices)):
                weightedAskPrices.append(ask_prices[i]*ask_volumes[i])
            averageAskPrice = (np.array(weightedAskPrices).mean())/sum(ask_volumes)

            weightedBidPrices = []
            for i in range(len(bid_prices)):
                weightedBidPrices.append(bid_prices[i]*bid_volumes[i])
            averageBidPrice = (np.array(weightedBidPrices).mean())/sum(bid_volumes)

            self.askPrice = averageAskPrice
            self.bidPrice = averageBidPrice

            allPrices = np.arry(np.concatenate(np.array(weightedAskPrices), np.array(weightedBidPrices)))
            allVolumes = sum(ask_volumes) + sum(bid_volumes)
            newMiddlePrice = (allPrices.mean()) / allVolumes

            if self.middlePrice > newMiddlePrice:
                self.priceDirection = -1
            else:
                self.priceDirection = 1

            gapToTheo = newMiddlePrice - (self.middlePrice + newMiddlePrice)/2.0

            self.theoPrice = newMiddlePrice + gapToTheo



        pass

    def on_order_status_message(self, client_order_id: int, fill_volume: int, remaining_volume: int, fees: int) -> None:
        """Called when the status of one of your orders changes.

        The fill_volume is the number of lots already traded, remaining_volume
        is the number of lots yet to be traded and fees is the total fees for
        this order. Remember that you pay fees for being a market taker, but
        you receive fees for being a market maker, so fees can be negative.

        If an order is cancelled its remaining volume will be zero.
        """
        pass

    def on_position_change_message(self, future_position: int, etf_position: int) -> None:
        """Called when your position changes.

        Since every trade in the ETF is automatically hedged in the future,
        future_position and etf_position will always be the inverse of each
        other (i.e. future_position == -1 * etf_position).
        """
        pass

    def on_trade_ticks_message(self, instrument: int, trade_ticks: List[Tuple[int, int]]) -> None:
        """Called periodically to report trading activity on the market.

        Each trade tick is a pair containing a price and the number of lots
        traded at that price since the last trade ticks message.
        """
        pass
