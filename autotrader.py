import asyncio
import numpy as np
import statistics
import itertools

from typing import List, Tuple

from ready_trader_one import BaseAutoTrader, Instrument, Lifespan, Side


class AutoTrader(BaseAutoTrader):

    # Limits
    activeOrderLimit = 10
    ordersPerSecondLimit = 20
    activeVolumeLimit = 200
    positionLimit = 100

    # Counters
    ordersThisSecond = 0
    currentActiveOrders = 0
    currentPositionStanding = 0
    currentPositionIDs = []
    currentPositionPrices = []
    currentPositionVolumes = []
    currentPositionDirections = []
    highestSequenceNum = -1
    orderIDs = 1

    # States
    bidPrice = 0
    askPrice = 0
    middlePrice = 0
    theoPrice = 0
    previousPrices = []
    priceMovingAverage = 0
    priceDirection = 0

    # Parameters
    desiredSpread = 0.001

    def __init__(self, loop: asyncio.AbstractEventLoop):
        """Initialise a new instance of the AutoTrader class."""
        super(AutoTrader, self).__init__(loop)
        self.time = self.event_loop.time()
    
    def addOrder(self, client_order_id: int, side: Side, price: int, volume: int):
        self.orderIDs += 1
        self.currentActiveOrders += 1
        self.currentPositionIDs.append(client_order_id)
        self.currentPositionDirections.append(side)
        self.currentPositionPrices.append(price)
        self.currentPositionVolumes.append(volume)
        return

    def on_error_message(self, client_order_id: int, error_message: bytes) -> None:
        """Called when the exchange detects an error.

        If the error pertains to a particular order, then the client_order_id
        will identify that order, otherwise the client_order_id will be zero.
        """
        if client_order_id in self.currentPositionIDs:
            index = self.currentPositionIDs.index(client_order_id)
            if self.currentPositionDirections[index] == Side.BUY:
                print("Error buying")
        pass

    def on_order_book_update_message(self, instrument: int, sequence_number: int, ask_prices: List[int],
                                     ask_volumes: List[int], bid_prices: List[int], bid_volumes: List[int]) -> None:
        """Called periodically to report the status of an order book.

        The sequence number can be used to detect missed or out-of-order
        messages. The five best available ask (i.e. sell) and bid (i.e. buy)
        prices are reported along with the volume available at each of those
        price levels.
        """
        if sequence_number < self.highestSequenceNum:
            return
        else:
            self.highestSequenceNum = sequence_number

        if sum(ask_volumes) == 0 or sum(bid_volumes) == 0:
            return

        if self.time == int(self.event_loop.time()):
            if self.ordersThisSecond > 19:
                return
        else:
            self.time = int(self.event_loop.time())
            self.ordersThisSecond = 0

        if instrument == Instrument.FUTURE:
            weightedAskPrices = []
            for i in range(len(ask_prices)):
                if(ask_prices[i] == 0) :
                    continue
                weightedAskPrices.append(ask_prices[i]*ask_volumes[i])
            averageAskPrice = (statistics.mean(weightedAskPrices))/sum(ask_volumes)

            weightedBidPrices = []
            for i in range(len(bid_prices)):
                if(bid_prices[i] == 0) :
                    continue
                weightedBidPrices.append(bid_prices[i]*bid_volumes[i])
            averageBidPrice = (statistics.mean(weightedBidPrices))/sum(bid_volumes)

            self.askPrice = averageAskPrice/.2
            self.bidPrice = averageBidPrice/.2

            print("Current position: {}".format(self.currentPositionStanding))
            print("Average ask: {}\nAverage bid: {}".format(self.askPrice, self.bidPrice))

            newMiddlePrice = statistics.mean([self.askPrice, self.bidPrice])

            if self.middlePrice == 0 and self.theoPrice == 0:
                self.middlePrice = newMiddlePrice
                self.theoPrice = newMiddlePrice

            if self.middlePrice > newMiddlePrice:
                self.priceDirection = -1
            else:
                self.priceDirection = 1

            gapToTheo = abs(newMiddlePrice - (self.middlePrice + newMiddlePrice)/2.0)*2

            self.theoPrice = round((self.theoPrice + (newMiddlePrice + self.priceDirection*(gapToTheo)))/2.0)
            self.middlePrice = newMiddlePrice

            print("Theo price: {}".format(self.theoPrice))

            minSell = round(self.theoPrice + self.theoPrice*self.desiredSpread)
            maxBuy = round(self.theoPrice - self.theoPrice*self.desiredSpread)
            print("Min sell: {}     Max buy: {}".format(minSell, maxBuy))
            print("")

            # Making orders
            if self.currentActiveOrders > 9:
                # Consider cancelling
                for i in range(len(self.currentPositionPrices)):
                    if self.currentPositionDirections[i] == Side.BUY:
                        if self.currentPositionPrices[i] > maxBuy:
                            self.send_cancel_order(self.currentPositionIDs[i])
                            self.ordersThisSecond += 1
                            if self.ordersThisSecond > 19:
                                return
                    else:
                        if self.currentPositionPrices[i] < minSell:
                            self.send_cancel_order(self.currentPositionIDs[i])
                            self.ordersThisSecond += 1
                            if self.ordersThisSecond > 19:
                                return
                # Consider waiting
            elif self.currentPositionStanding < (-1*self.positionLimit + 10):
                # Consider cancelling sell orders
                for i in range(len(self.currentPositionPrices)):
                    if self.currentPositionDirections[i] == Side.SELL:
                        if self.currentPositionPrices[i] < minSell:
                            self.send_cancel_order(self.currentPositionIDs[i])
                            self.ordersThisSecond += 1
                            if self.ordersThisSecond > 19:
                                return
                # Consider buying
                for i in range(len(ask_prices)):
                    if(ask_prices[i] == 0) :
                        continue
                    if ask_prices[i] <= maxBuy:
                        self.send_insert_order(self.orderIDs, Side.BUY, ask_prices[i], 1, Lifespan.FILL_AND_KILL)
                        self.addOrder(self.orderIDs, Side.BUY, ask_prices[i], 1)
                        self.ordersThisSecond += 1
                        if self.ordersThisSecond > 19:
                            return
            elif self.currentPositionStanding > (self.positionLimit - 10):
                # Consider cancelling buy orders
                for i in range(len(self.currentPositionPrices)):
                    if self.currentPositionDirections[i] == Side.BUY:
                        if self.currentPositionPrices[i] > maxBuy:
                            self.send_cancel_order(self.currentPositionIDs[i])
                            self.ordersThisSecond += 1
                            if self.ordersThisSecond > 19:
                                return
                # Consider selling
                for i in range(len(bid_prices)):
                    if(bid_prices[i] == 0) :
                        continue
                    if bid_prices[i] >= minSell:
                        self.send_insert_order(self.orderIDs, Side.SELL, bid_prices[i], 1, Lifespan.FILL_AND_KILL)
                        self.addOrder(self.orderIDs, Side.SELL, bid_prices[i], 1)
                        self.ordersThisSecond += 1
                        if self.ordersThisSecond > 19:
                            return
            else:
                for i in range(len(ask_prices)):
                    if(ask_prices[i] == 0) :
                        continue
                    if ask_prices[i] <= maxBuy:
                        self.send_insert_order(self.orderIDs, Side.BUY, ask_prices[i], 1, Lifespan.FILL_AND_KILL)
                        self.addOrder(self.orderIDs, Side.BUY, ask_prices[i], 1)
                        self.ordersThisSecond += 1
                        if self.ordersThisSecond > 19:
                            return
                        return
                for i in range(len(bid_prices)):
                    if(bid_prices[i] == 0) :
                        continue
                    if bid_prices[i] >= minSell:
                        self.send_insert_order(self.orderIDs, Side.SELL, bid_prices[i], 1, Lifespan.FILL_AND_KILL)
                        self.addOrder(self.orderIDs, Side.SELL, bid_prices[i], 1)
                        self.ordersThisSecond += 1
                        if self.ordersThisSecond > 19:
                            return
                        return
                
                # Place new orders
                if self.currentPositionStanding > 10:
                    self.send_insert_order(self.orderIDs, Side.SELL, round(minSell, -2), 1, Lifespan.GOOD_FOR_DAY)
                    self.addOrder(self.orderIDs, Side.SELL, round(minSell, -2), 1)
                elif self.currentPositionStanding < -10:
                    self.send_insert_order(self.orderIDs, Side.BUY, round(maxBuy, -2), 1, Lifespan.GOOD_FOR_DAY)
                    self.addOrder(self.orderIDs, Side.BUY, round(maxBuy, -2), 1)
                else:
                    self.send_insert_order(self.orderIDs, Side.SELL, round(minSell, -2), 1, Lifespan.GOOD_FOR_DAY)
                    self.addOrder(self.orderIDs, Side.SELL, round(minSell, -2), 1)
                    self.ordersThisSecond += 1
                    if self.ordersThisSecond > 19:
                        return
                    self.send_insert_order(self.orderIDs, Side.BUY, round(maxBuy, -2), 1, Lifespan.GOOD_FOR_DAY)
                    self.addOrder(self.orderIDs, Side.BUY, round(maxBuy, -2), 1)
                self.ordersThisSecond += 1
                if self.ordersThisSecond > 19:
                    return
        return

    def on_order_status_message(self, client_order_id: int, fill_volume: int, remaining_volume: int, fees: int) -> None:
        """Called when the status of one of your orders changes.

        The fill_volume is the number of lots already traded, remaining_volume
        is the number of lots yet to be traded and fees is the total fees for
        this order. Remember that you pay fees for being a market taker, but
        you receive fees for being a market maker, so fees can be negative.

        If an order is cancelled its remaining volume will be zero.
        """
        if not client_order_id in self.currentPositionIDs:
            return

        if remaining_volume == 0:
            self.currentActiveOrders -= 1
            indexInPositions = self.currentPositionIDs.index(client_order_id)
            self.currentPositionDirections.pop(indexInPositions)
            self.currentPositionIDs.pop(indexInPositions)
            self.currentPositionPrices.pop(indexInPositions)
            self.currentPositionVolumes.pop(indexInPositions)
        elif fill_volume > 0:
            indexInPositions = self.currentPositionIDs.index(client_order_id)
            self.currentPositionVolumes[indexInPositions] = remaining_volume
        return

    def on_position_change_message(self, future_position: int, etf_position: int) -> None:
        """Called when your position changes.

        Since every trade in the ETF is automatically hedged in the future,
        future_position and etf_position will always be the inverse of each
        other (i.e. future_position == -1 * etf_position).
        """
        self.currentPositionStanding = etf_position
        return

    def on_trade_ticks_message(self, instrument: int, trade_ticks: List[Tuple[int, int]]) -> None:
        """Called periodically to report trading activity on the market.

        Each trade tick is a pair containing a price and the number of lots
        traded at that price since the last trade ticks message.
        """

        self.time = self.event_loop.time()

        if instrument == Instrument.FUTURE:
            highestVolume = -1
            priceAtVolume = -1
            for i in range(len(trade_ticks)):
                if trade_ticks[i][1] > highestVolume:
                    highestVolume = trade_ticks[i][1]
                    priceAtVolume = trade_ticks[i][0]
            theoPriceAdjustment = (priceAtVolume - self.theoPrice)*0.1
            self.theoPrice += theoPriceAdjustment
        return
