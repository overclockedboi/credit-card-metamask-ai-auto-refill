// Create the wallet icon component using inline SVG
const WalletIcon = ({ className }) => {
    return React.createElement('svg', {
        xmlns: 'http://www.w3.org/2000/svg',
        width: '24',
        height: '24',
        viewBox: '0 0 24 24',
        fill: 'none',
        stroke: 'currentColor',
        strokeWidth: '2',
        strokeLinecap: 'round',
        strokeLinejoin: 'round',
        className
    }, [
        React.createElement('path', {
            key: 'path1',
            d: 'M20 12V8H6a2 2 0 0 1-2-2c0-1.1.9-2 2-2h12v4'
        }),
        React.createElement('path', {
            key: 'path2',
            d: 'M4 6v12c0 1.1.9 2 2 2h14v-4'
        }),
        React.createElement('path', {
            key: 'path3',
            d: 'M18 12a2 2 0 0 0-2 2c0 1.1.9 2 2 2h4v-4h-4z'
        })
    ]);
};

const App = () => {
    const [cardBalance, setCardBalance] = React.useState(0);
    const [ethBalance, setEthBalance] = React.useState(0);
    const [ethPrice, setEthPrice] = React.useState(0);
    const [metamaskBalanceUSD, setMetamaskBalanceUSD] = React.useState(0);
    const [tradingSuggestion, setTradingSuggestion] = React.useState(null);
    const [isConnected, setIsConnected] = React.useState(false);
    const [web3, setWeb3] = React.useState(null);
    const [accounts, setAccounts] = React.useState([]);
    const [notification, setNotification] = React.useState(null);
    const [withdrawAmount, setWithdrawAmount] = React.useState('');
    const [gasPrice, setGasPrice] = React.useState(0);
    const [minProfitableAmount, setMinProfitableAmount] = React.useState(0);

    const fetchBalance = React.useCallback(async () => {
        if (!accounts[0]) return;

        try {
            const response = await fetch(`/status?wallet_address=${accounts[0]}`);
            const data = await response.json();
            if (response.ok) {
                setCardBalance(data.card_balance);
                setEthBalance(data.eth_balance);
                setEthPrice(data.eth_price);
                setGasPrice(data.gas_price_gwei);
                setMinProfitableAmount(data.min_profitable_amount);
                setMetamaskBalanceUSD(data.metamask_balance_usd);
                setTradingSuggestion(data.trading_suggestion);

                // Show notification if auto top-up is needed
                if (data.decision && data.decision.action === 'top-up') {
                    setNotification({
                        type: 'warning',
                        message: `Low card balance! ${data.decision.reason}. Auto top-up amount: $${data.decision.amount}`
                    });
                }
            }
        } catch (error) {
            console.error('Error fetching balance:', error);
        }
    }, [accounts]);

    React.useEffect(() => {
        if (window.ethereum) {
            const web3Instance = new Web3(window.ethereum);
            setWeb3(web3Instance);
        }
    }, []);

    React.useEffect(() => {
        // Initial balance fetch
        fetchBalance();

        // Set up periodic balance updates
        const interval = setInterval(fetchBalance, 30000); // Update every 30 seconds
        return () => clearInterval(interval);
    }, [fetchBalance]);

    const handleConnectWallet = async () => {
        if (web3) {
            try {
                const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
                setAccounts(accounts);
                setIsConnected(true);
                setNotification({ type: 'success', message: 'Wallet connected successfully!' });

                // Fetch initial balances
                fetchBalance();
            } catch (error) {
                setNotification({ type: 'error', message: error.message });
            }
        }
    };

    const handleDisconnectWallet = () => {
        setIsConnected(false);
        setAccounts([]);
        setMetamaskBalanceUSD(0);
        setNotification({ type: 'info', message: 'Wallet disconnected' });
    };

    const handleWithdraw = async (e) => {
        e.preventDefault();
        if (!isConnected) {
            setNotification({ type: 'error', message: 'Please connect your wallet first' });
            return;
        }

        const amount = parseFloat(withdrawAmount);
        if (isNaN(amount) || amount <= 0) {
            setNotification({ type: 'error', message: 'Please enter a valid amount' });
            return;
        }

        try {
            const response = await fetch('/use-card', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    amount: amount,
                    currency: 'USD',
                    wallet_address: accounts[0]
                })
            });
            const data = await response.json();
            if (response.ok) {
                setCardBalance(data.new_balance);
                setMetamaskBalanceUSD(data.new_metamask_balance_usd);
                setEthBalance(data.new_eth_balance);
                setWithdrawAmount(''); // Reset input after successful withdrawal

                setNotification({
                    type: 'success',
                    message: `Withdrawal successful: $${amount}. New card balance: $${data.new_balance.toFixed(2)}, New MetaMask balance: $${data.new_metamask_balance_usd.toFixed(2)}`
                });
            } else {
                throw new Error(data.detail || 'Transaction failed');
            }
        } catch (error) {
            setNotification({ type: 'error', message: error.message });
        }
    };

    return (
        <div className="container mx-auto p-4 pt-6 md:p-6 lg:p-12 xl:p-24">
            {notification && (
                <div className={`mb-4 p-4 rounded-lg ${notification.type === 'success' ? 'bg-green-900 text-green-200' :
                    notification.type === 'error' ? 'bg-red-900 text-red-200' :
                        notification.type === 'warning' ? 'bg-yellow-900 text-yellow-200' :
                            'bg-blue-900 text-blue-200'
                    }`}>
                    {notification.message}
                </div>
            )}

            <div className="bg-gray-900 rounded-xl shadow-lg p-6 border border-gray-800">
                <h1 className="text-3xl font-bold mb-6 flex items-center text-white">
                    <WalletIcon className="w-8 h-8 mr-2" />
                    OrbitX Card
                </h1>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                    <div className="bg-gray-800 p-4 rounded-lg border border-gray-700" style={{
                        backgroundImage: 'url("https://framerusercontent.com/images/jZe65xeCgciZaxsQZS1e0Rk3Ic.png?scale-down-to=512")',
                        backgroundSize: '150px',
                        backgroundRepeat: 'no-repeat',
                        backgroundPosition: 'right bottom',
                        backgroundOpacity: '0.1'
                    }}>
                        <h2 className="text-xl font-semibold mb-2 text-gray-300">OrbitX Card Balance</h2>
                        <p className="text-3xl font-bold text-white">
                            ${cardBalance}
                        </p>
                    </div>

                    <div className="bg-gray-800 p-4 rounded-lg border border-gray-700" style={{
                        backgroundImage: 'url("https://upload.wikimedia.org/wikipedia/commons/thumb/3/36/MetaMask_Fox.svg/1200px-MetaMask_Fox.svg.png")',
                        backgroundSize: '100px',
                        backgroundRepeat: 'no-repeat',
                        backgroundPosition: 'right center',
                        backgroundOpacity: '0.1'
                    }}>
                        <h2 className="text-xl font-semibold mb-2 text-gray-300">MetaMask Balance</h2>
                        <div>
                            <p className="text-3xl font-bold text-white">
                                ${metamaskBalanceUSD.toFixed(2)}
                            </p>
                            <p className="text-gray-400">
                                {ethBalance.toFixed(4)} ETH @ ${ethPrice.toFixed(2)}
                            </p>
                        </div>
                    </div>
                </div>

                {isConnected ? (
                    <div>
                        <div className="bg-gray-800 p-4 rounded-lg mb-4 border border-gray-700">
                            <p className="text-gray-400">Connected Account:</p>
                            <p className="font-mono text-sm text-gray-300">{accounts[0]}</p>
                            <div className="mt-2 grid grid-cols-2 gap-4 text-sm">
                                <div>
                                    <p className="text-gray-400">Gas Price:</p>
                                    <p className="font-semibold text-gray-300">{gasPrice.toFixed(2)} Gwei</p>
                                </div>
                                <div>
                                    <p className="text-gray-400">Minimum Withdrawal:</p>
                                    <p className="font-semibold text-gray-300">${minProfitableAmount}</p>
                                </div>
                            </div>
                        </div>

                        <div className="bg-gray-800 p-4 rounded-lg border border-gray-700 mt-4">
                            <h3 className="text-lg font-semibold mb-2 text-gray-300">AI Trading Suggestion</h3>
                            {tradingSuggestion && (
                                <>
                                    <div className={`text-lg font-bold ${tradingSuggestion.action === 'buy' ? 'text-green-400' :
                                        tradingSuggestion.action === 'sell' ? 'text-red-400' :
                                            'text-yellow-400'
                                        }`}>
                                        {tradingSuggestion.action.toUpperCase()}: {tradingSuggestion.amount} ETH
                                    </div>
                                    <p className="text-gray-400 mt-2">{tradingSuggestion.reason}</p>
                                </>
                            )}
                        </div>

                        <form onSubmit={handleWithdraw} className="mt-4">
                            <div className="mb-4">
                                <label htmlFor="withdrawAmount" className="block text-sm font-medium text-gray-300 mb-2">
                                    Withdrawal Amount (USD) - Minimum: ${minProfitableAmount}
                                </label>
                                <div className="relative rounded-md shadow-sm">
                                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                        <span className="text-gray-500 sm:text-sm">$</span>
                                    </div>
                                    <input
                                        type="number"
                                        name="withdrawAmount"
                                        id="withdrawAmount"
                                        min={minProfitableAmount}
                                        step="0.01"
                                        required
                                        className="bg-gray-800 focus:ring-blue-500 focus:border-blue-500 block w-full pl-7 pr-12 sm:text-sm border-gray-700 rounded-md text-white"
                                        placeholder={minProfitableAmount.toString()}
                                        value={withdrawAmount}
                                        onChange={(e) => setWithdrawAmount(e.target.value)}
                                    />
                                    <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none">
                                        <span className="text-gray-500 sm:text-sm">USD</span>
                                    </div>
                                </div>
                                <p className="mt-1 text-sm text-gray-400">
                                    Amount must be at least ${minProfitableAmount} to cover gas fees and ensure profitability
                                </p>
                            </div>
                            <button
                                type="submit"
                                disabled={parseFloat(withdrawAmount) < minProfitableAmount}
                                className={`w-full font-medium py-3 px-4 rounded-lg transition duration-150 ease-in-out mb-4 
                                    ${parseFloat(withdrawAmount) >= minProfitableAmount
                                        ? 'bg-blue-600 hover:bg-blue-700 text-white'
                                        : 'bg-gray-700 text-gray-400 cursor-not-allowed'
                                    }`}
                            >
                                Withdraw
                            </button>
                        </form>

                        <button
                            onClick={handleDisconnectWallet}
                            className="w-full bg-red-900 hover:bg-red-800 text-white font-medium py-3 px-4 rounded-lg transition duration-150 ease-in-out border border-red-700"
                        >
                            Disconnect Wallet
                        </button>
                    </div >
                ) : (
                    <div>
                        <button
                            onClick={handleConnectWallet}
                            className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-3 px-4 rounded-lg transition duration-150 ease-in-out"
                        >
                            Connect MetaMask Wallet
                        </button>
                        <p className="text-sm text-gray-400 text-center mt-4">
                            Connect your wallet to use OrbitX Card
                        </p>
                    </div>
                )}
            </div >
        </div >
    );
};

// Use the global ReactDOM object
ReactDOM.render(React.createElement(App), document.getElementById('root')); 