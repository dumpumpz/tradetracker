javascript
document.addEventListener('DOMContentLoaded', () => {

    // --- CONFIGURATION ---
    const CONFIG = {
        FIREBASE: {
            apiKey: "AIzaSyCQ4vHqGiv_yRkA0zZaaOU24gxhqBkxnv4", // <-- REPLACE THIS
            authDomain: "journal-a003f.firebaseapp.com",
            databaseURL: "https://journal-a003f-default-rtdb.asia-southeast1.firebasedatabase.app",
            projectId: "journal-a003f",
            storageBucket: "journal-a003f.firebasestorage.app",
            messagingSenderId: "1038636626553",
            appId: "1:1038636626553:web:7a91c321e39c146bdc9aa8"
        },
        DB_PATHS: {
            TRADES: 'trades',
            COMPLETED_TRADES: 'completed_trades',
            BANK: 'bank',
            JOURNAL_TEXT: 'journal_text',
            JOURNAL_IMAGES: 'journal_images',
            IMAGE_LIBRARY: 'image_library',
            SETUPS_IMAGES: 'setups_images',
            CHART_LIBRARY_2: 'chart_library_2',
            JOURNAL_FAVOURITES: 'journal_favourites',
            SETUPS_1: 'current_setups_1',
            SETUPS_2: 'current_setups_2',
            PERSISTENT_NOTES: 'persistent_notes',
            TRACKER_SCRATCHPAD: 'tracker_scratchpad',
            SENTIMENT_RECEIPTS: 'sentiment_receipts',
            LEVEL_NOTES: 'level_notes',
            GENERAL_NOTES: 'general_notes'
        },
        TRADE_SETTINGS: {
            FEE_RATE: 0.00075,
            STARTING_BALANCE: 3881,
        },
        EMA_ANALYSIS: {
            SYMBOLS: ['BTC-USDT', 'ETH-USDT'],
            TIMEFRAMES: ['1hour', '2hour', '4hour', 'daily'],
            PERIODS: [13, 49, 100, 200, 500, 1000],
            SHORT_NAMES: {'15min': '15m', '30min': '30m', '1hour': '1H', '2hour': '2H', '4hour': '4H', 'daily': '1D', 'weekly': '1W', 'monthly': '1M'}
        }
    };

    const CL2_FOLDERS = ['monthly', 'weekly', 'daily', '4hour', '2hour', '1hour', '30min', '15min', '5min'];

    // --- DOM ELEMENT CACHE ---
    const DOM = {
        tabs: document.querySelector('.tabs'),
        themeToggle: document.getElementById('theme-checkbox'),
        trackerTab: document.getElementById('tracker-tab'),
        tradeImageUploader: document.getElementById('trade-image-uploader'),
        statsPanelContainer: document.getElementById('stats-panel-container'),
        statsFab: document.getElementById('stats-fab'),
        statsPanel: document.getElementById('stats-panel'),
        closeStatsBtn: document.getElementById('close-stats-btn'),
        statBalance: document.getElementById('stat-balance'),
        statBalanceAud: document.getElementById('stat-balance-aud'),
        statTotalPl: document.getElementById('stat-total-pl'),
        statTotalPlAud: document.getElementById('stat-total-pl-aud'),
        statCompletedTrades: document.getElementById('stat-completed-trades'),
        statWins: document.getElementById('stat-wins'),
        statLosses: document.getElementById('stat-losses'),
        statWinRate: document.getElementById('stat-win-rate'),
        statProfitFactor: document.getElementById('stat-profit-factor'),
        statAvgWin: document.getElementById('stat-avg-win'),
        statAvgLoss: document.getElementById('stat-avg-loss'),
        statRewardRisk: document.getElementById('stat-reward-risk'),
        statOpenTrades: document.getElementById('stat-open-trades'),
        keyOpensLastUpdated: document.querySelector('#key-opens-last-updated span'),
        btcDailyOpen: document.getElementById('btc-daily-open'),
        btcWeeklyOpen: document.getElementById('btc-weekly-open'),
        btcMonthlyOpen: document.getElementById('btc-monthly-open'),
        ethDailyOpen: document.getElementById('eth-daily-open'),
        ethWeeklyOpen: document.getElementById('eth-weekly-open'),
        ethMonthlyOpen: document.getElementById('eth-monthly-open'),
        trackerScratchpadEl: document.getElementById('tracker-scratchpad'),
        addTradeForm: document.getElementById('add-trade-form'),
        tradesTbody: document.getElementById('trades-tbody'),
        completedTradesTbody: document.getElementById('completed-trades-tbody'),
        assetSentimentContainer: document.getElementById('asset-sentiment-container'),
        sentimentReceiptsTbody: document.getElementById('sentiment-receipts-tbody'),
        emaSnapshotContainer: document.getElementById('ema-snapshot-container'),
        chartLibrary2Container: document.getElementById('chart-library-2-container'),
        chartLibrary2PreviewContainer: document.getElementById('chart-library-2-preview-container'),
        imageLibraryContainer: document.getElementById('image-library-container'),
        libraryImageUpload: document.getElementById('library-image-upload'),
        libraryUploadProgress: document.getElementById('library-upload-progress'),
        setupsImageContainer: document.getElementById('setups-image-container'),
        setupsImageUpload: document.getElementById('setups-image-upload'),
        setupsUploadProgress: document.getElementById('setups-upload-progress'),
        imageModal: document.getElementById('image-modal'),
        modalImageContent: document.getElementById('modal-image-content'),
        modalClose: document.querySelector('.modal-close'),
        modalCaption: document.getElementById('modal-caption'),
        modalPrevBtn: document.getElementById('modal-prev'),
        modalNextBtn: document.getElementById('modal-next'),
        journalTab: document.getElementById('journal-tab'),
        chartsTab: document.getElementById('charts-tab'),
        notesTab: document.getElementById('notes-tab'),
        createNewNoteBtn: document.getElementById('create-new-note-btn'),
        notesContainer: document.getElementById('notes-container'),
        persistentNotesEl: document.getElementById('persistent-notes-entry'),
        setupsTable1: document.getElementById('primary-setups-table'),
        setupsTable2: document.getElementById('secondary-setups-table'),
        primarySetupsNotes: document.getElementById('primary-setups-notes'),
        secondarySetupsNotes: document.getElementById('secondary-setups-notes'),
        saveSetups1Btn: document.getElementById('save-setups-1-btn'),
        saveSetups2Btn: document.getElementById('save-setups-2-btn'),
        setupsSaveStatus1: document.getElementById('setups-save-status-1'),
        setupsSaveStatus2: document.getElementById('setups-save-status-2'),
        journalSymbolEl: document.getElementById('journal-symbol'),
        journalTimeframeEl: document.getElementById('journal-timeframe'),
        journalImageFilterEl: document.getElementById('journal-image-filter'),
        dateButtonsContainer: document.getElementById('date-buttons-container'),
        datePrevBtn: document.getElementById('date-prev'),
        dateNextBtn: document.getElementById('date-next'),
        favouritedEntryContainer: document.getElementById('favourited-entry-container'),
        favouritedEntryText: document.getElementById('favourited-entry-text'),
        favouriteBtn: document.getElementById('favourite-btn'),
        journalEntryEl: document.getElementById('journal-entry'),
        saveStatus: document.getElementById('save-status'),
        journalImageUpload: document.getElementById('journal-image-upload'),
        uploadProgress: document.getElementById('upload-progress'),
        journalImagesContainer: document.getElementById('journal-images-container'),
        srLevelsTab: document.getElementById('sr-levels-tab'),
        srLegendHeader: document.getElementById('sr-legend-header'),
        srLegendContent: document.getElementById('sr-legend-content'),
        srLegendToggleBtn: document.getElementById('sr-legend-toggle-btn'),
        srLastUpdatedTime: document.getElementById('sr-last-updated-time'),
        srMetadataDates: document.getElementById('sr-metadata-dates'),
        srMetadataTimeframes: document.getElementById('sr-metadata-timeframes'),
        srMetadataWindows: document.getElementById('sr-metadata-windows'),
        srSymbolEl: document.getElementById('sr-symbol'),
        srLookbackEl: document.getElementById('sr-lookback'),
        supportLevelsTbody: document.getElementById('support-levels-tbody'),
        resistanceLevelsTbody: document.getElementById('resistance-levels-tbody'),
        noteEditModal: document.getElementById('note-edit-modal'),
        noteModalTitle: document.getElementById('note-modal-title'),
        noteModalContent: document.getElementById('note-modal-content'),
        noteModalClose: document.getElementById('note-modal-close'),
        optionsOiTab: document.getElementById('options-oi-tab'),
    };

    // --- APPLICATION STATE ---
    const STATE = {
        isMasterUser: false,
        masterPassword: null,
        viewerId: null,
        usdToAudRate: 1.53,
        marketOpens: {},
        journalText: {},
        journalImages: {},
        chartLibrary2Data: {}, 
        currentCl2Folder: null,
        emaData: {},
        srData: {},
        favouriteEntries: {},
        persistentNotes: '',
        trackerScratchpadText: '',
        setupsData1: {},
        setupsData2: {},
        generalNotes: {},
        selectedDate: null,
        centerDate: null,
        journalSaveTimer: null,
        notesSaveTimer: null,
        trackerSaveTimer: null,
        setups1NotesTimer: null,
        setups2NotesTimer: null,
        isMerging: false,
        mergeBaseTradeId: null,
        modalImageGallery: [],
        modalImageIndex: -1,
        imageUploadContext: {
            id: null,
            type: null 
        },
        levelNotes: {},
        levelNotesSaveTimer: null,
        allSentimentReceipts: {},
        sentimentShowAll: false,
        sentimentCurrentPage: 1,
        sentimentItemsPerPage: 15,
    };

    // --- INITIALIZE FIREBASE ---
    firebase.initializeApp(CONFIG.FIREBASE);
    const database = firebase.database();
    const storage = firebase.storage();

    const dbRefs = {
        trades: database.ref(CONFIG.DB_PATHS.TRADES),
        completedTrades: database.ref(CONFIG.DB_PATHS.COMPLETED_TRADES),
        bank: database.ref(CONFIG.DB_PATHS.BANK),
        journalText: database.ref(CONFIG.DB_PATHS.JOURNAL_TEXT),
        journalImages: database.ref(CONFIG.DB_PATHS.JOURNAL_IMAGES),
        imageLibrary: database.ref(CONFIG.DB_PATHS.IMAGE_LIBRARY),
        setupsImages: database.ref(CONFIG.DB_PATHS.SETUPS_IMAGES), 
        chartLibrary2: database.ref(CONFIG.DB_PATHS.CHART_LIBRARY_2),
        favourites: database.ref(CONFIG.DB_PATHS.JOURNAL_FAVOURITES),
        setups1: database.ref(CONFIG.DB_PATHS.SETUPS_1),
        setups2: database.ref(CONFIG.DB_PATHS.SETUPS_2),
        persistentNotes: database.ref(CONFIG.DB_PATHS.PERSISTENT_NOTES),
        trackerScratchpad: database.ref(CONFIG.DB_PATHS.TRACKER_SCRATCHPAD),
        sentimentReceipts: database.ref(CONFIG.DB_PATHS.SENTIMENT_RECEIPTS),
        levelNotes: database.ref(CONFIG.DB_PATHS.LEVEL_NOTES),
        generalNotes: database.ref(CONFIG.DB_PATHS.GENERAL_NOTES)
    };

    // --- HELPER FUNCTIONS ---
    const debounce = (func, delay) => {
        let timeout;
        return (...args) => {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), delay);
        };
    };

    function autoResizeTextarea(textarea) {
        if (!textarea || textarea.tagName !== 'TEXTAREA') return;
        textarea.style.height = 'auto';
        textarea.style.height = `${textarea.scrollHeight}px`;
    }

    function resizeParentCollapsible(elementInside) {
        const section = elementInside.closest('.collapsible-section');
        if (section && section.classList.contains('is-open')) {
            const content = section.querySelector('.collapsible-content');
            if (content) {
                content.style.maxHeight = content.scrollHeight + 'px';
            }
        }
    }
    
    const debouncedResizeParent = debounce(resizeParentCollapsible, 250);

    const formatCurrency = (num, symbol = '$') => {
        if (typeof num !== 'number' || isNaN(num)) {
            return '--';
        }
        const maximumFractionDigits = num > 100 ? 2 : (num > 1 ? 4 : 8);
        return `${symbol}${num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits })}`;
    };

    function adjustCollapsibleSize(elementInside) {
        if (!elementInside) return;
        if (elementInside.tagName === 'TEXTAREA') {
            autoResizeTextarea(elementInside);
        }
        resizeParentCollapsible(elementInside);
    }

    const getYYYYMMDD = (date) => date.toISOString().split('T')[0];

    const getPerthDateString = (date = new Date()) => {
        try {
            const formatter = new Intl.DateTimeFormat('en-CA', {
                timeZone: 'Australia/Perth',
                year: 'numeric',
                month: '2-digit',
                day: '2-digit'
            });
            return formatter.format(date);
        } catch (e) {
            console.error("Timezone formatting failed, using fallback.", e);
            const perthTime = new Date(date.getTime() + (8 * 60 * 60 * 1000));
            return perthTime.toISOString().split('T')[0];
        }
    };

    const getSafeSymbol = (symbol) => symbol.replace(/\//g, '-');

    function getViewerId() {
        if (STATE.viewerId) return STATE.viewerId;
        let id = localStorage.getItem('viewerId');
        if (!id) {
            id = `viewer_${Date.now()}_${Math.random().toString(36).substring(2, 10)}`;
            localStorage.setItem('viewerId', id);
        }
        STATE.viewerId = id;
        return id;
    }

    // --- DATA FETCHING ---
    async function fetchLiveConversionRate() {
        try {
            const response = await fetch('https://open.er-api.com/v6/latest/USD');
            if (!response.ok) return;
            const data = await response.json();
            if (data?.result === "success" && data?.rates?.AUD) {
                STATE.usdToAudRate = data.rates.AUD;
            }
        } catch (error) {
            console.error("Could not fetch conversion rate.", error);
        }
    }

    async function fetchEmaData() {
        try {
            const response = await fetch(`ma_analysis.json?cache_bust=${new Date().getTime()}`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            STATE.emaData = await response.json();
            renderEmaSnapshot('BTC-USDT');
        } catch (error) {
            console.error("Could not fetch ma_analysis.json:", error);
            if (DOM.emaSnapshotContainer) DOM.emaSnapshotContainer.innerHTML = '<p style="color: red; text-align: center;">Error loading EMA data.</p>';
        }
    }

    async function fetchSrData() {
        try {
            const response = await fetch(`sr_levels_analysis.json?cache_bust=${new Date().getTime()}`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            STATE.srData = await response.json();
            if (DOM.srLevelsTab.classList.contains('active')) {
                renderSrLevels();
            }
        } catch (error) {
            console.error("Could not fetch sr_levels_analysis.json:", error);
            DOM.supportLevelsTbody.parentElement.innerHTML = '<p style="color: red; text-align: center;">Error loading S/R data.</p>';
        }
    }

    async function fetchMarketOpens() {
        try {
            const response = await fetch(`market_opens.json?cache_bust=${new Date().getTime()}`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            STATE.marketOpens = await response.json();
            renderMarketOpens();
        } catch (error) {
            console.error("Could not fetch market_opens.json:", error);
        }
    }

    async function fetchCrossoverSignalData() {
        const signalJsonUrl = 'crypto_signals.json';
        try {
            const response = await fetch(`${signalJsonUrl}?cache_bust=${new Date().getTime()}`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const data = await response.json();
            renderCrossoverSignals(data);
        } catch (error) {
            console.error("Could not fetch or parse crossover signal data:", error);
            const ethContainer = document.getElementById('eth-crossover-signal-container');
            const btcContainer = document.getElementById('btc-crossover-signal-container');
            const errorMsg = '<p style="color: red; text-align: center;">Error loading signal data.</p>';
            if (ethContainer) ethContainer.innerHTML = errorMsg;
            if (btcContainer) btcContainer.innerHTML = errorMsg;
            const lastUpdatedEl = document.getElementById('crossover-signals-last-updated');
            if(lastUpdatedEl) lastUpdatedEl.textContent = 'Failed to load data.';
        }
    }

    async function fetchAndRenderOptionsData() {
        const container = DOM.optionsOiTab;
        if (!container) return;
    
        const jsonFile = 'deribit_options_market_analysis.json';
        try {
            const response = await fetch(`${jsonFile}?cache_bust=${new Date().getTime()}`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const data = await response.json();
    
            const spotPrice = data.metadata.btc_index_price_usd;
            const pcrData = data.metadata.put_call_ratio_24h_volume;
    
            // --- Helper Functions for Formatting ---
            const formatNum = (num, dec = 0) => num.toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec });
            const formatMoney = (num) => `$${formatNum(num)}`;
            const formatSkew = (skew) => {
                const val = (skew * 100).toFixed(2);
                const sign = skew > 0 ? '+' : '';
                const colorClass = skew > 0 ? 'positive' : (skew < 0 ? 'negative' : '');
                return `<span class="value ${colorClass}">${sign}${val}%</span>`;
            }
    
            // --- Build Header Stats ---
            const pcrRatio = pcrData.ratio_by_volume || 0;
            const pcrColorClass = pcrRatio > 0.7 ? 'negative' : (pcrRatio < 0.5 ? 'positive' : '');
            const headerStatsHtml = `
                <div class="options-header-stats">
                    <div class="header-stat-item">
                        <div class="header-stat-label">BTC Spot Price</div>
                        <div class="header-stat-value">${formatMoney(spotPrice)}</div>
                    </div>
                    <div class="header-stat-item">
                        <div class="header-stat-label">24h Put/Call Ratio (Volume)</div>
                        <div class="header-stat-value ${pcrColorClass}">${pcrRatio.toFixed(2)}</div>
                        <div class="pcr-note">Puts: ${formatNum(pcrData.put_volume_24h_btc, 2)} / Calls: ${formatNum(pcrData.call_volume_24h_btc, 2)}</div>
                    </div>
                </div>
            `;
    
            // --- Build Expiry Cards ---
            let expirationsHtml = '';
            const majorExpiries = data.expirations.filter(exp => ['Monthly', 'Quarterly'].includes(exp.option_type) || exp.notional_value_usd > 500000000);

            for (const expiry of majorExpiries) {
                // OI Walls
                const maxCallOi = Math.max(...expiry.open_interest_walls.top_call_strikes.map(s => s.open_interest_btc), 0);
                const maxPutOi = Math.max(...expiry.open_interest_walls.top_put_strikes.map(s => s.open_interest_btc), 0);

                const callsHtml = expiry.open_interest_walls.top_call_strikes.map(c => `
                    <div class="oi-wall-item">
                        <div class="oi-wall-strike">${formatMoney(c.strike)}</div>
                        <div class="oi-wall-bar-container">
                            <div class="oi-wall-bar-bg">
                                <div class="oi-wall-bar" style="width: ${(c.open_interest_btc / maxCallOi) * 100}%;"></div>
                                <div class="oi-wall-value">${formatNum(c.open_interest_btc)} BTC</div>
                            </div>
                        </div>
                    </div>
                `).join('');

                const putsHtml = expiry.open_interest_walls.top_put_strikes.map(p => `
                    <div class="oi-wall-item">
                        <div class="oi-wall-strike">${formatMoney(p.strike)}</div>
                        <div class="oi-wall-bar-container">
                            <div class="oi-wall-bar-bg">
                                <div class="oi-wall-bar" style="width: ${(p.open_interest_btc / maxPutOi) * 100}%;"></div>
                                <div class="oi-wall-value">${formatNum(p.open_interest_btc)} BTC</div>
                            </div>
                        </div>
                    </div>
                `).join('');

                // Gamma Chart
                const gammaRange = 0.15; // Show strikes within +/- 15% of spot
                const minStrikeRange = spotPrice * (1 - gammaRange);
                const maxStrikeRange = spotPrice * (1 + gammaRange);
                const relevantGamma = expiry.dealer_gamma_by_strike.filter(g => g.strike >= minStrikeRange && g.strike <= maxStrikeRange && g.dealer_gamma !== 0);
                
                let gammaChartHtml = '<p style="font-size:12px; text-align:center; color: var(--subtle-text);">No significant gamma near spot.</p>';
                if (relevantGamma.length > 0) {
                    const maxAbsGamma = Math.max(...relevantGamma.map(g => Math.abs(g.dealer_gamma)));
                    const chartStrikes = relevantGamma.map(g => g.strike);
                    const minChartStrike = Math.min(...chartStrikes);
                    const maxChartStrike = Math.max(...chartStrikes);
                    const spotPositionPercent = ((spotPrice - minChartStrike) / (maxChartStrike - minChartStrike)) * 100;
                    
                    const barsHtml = relevantGamma.map(g => {
                        const barHeight = (Math.abs(g.dealer_gamma) / maxAbsGamma) * 100;
                        const barClass = g.dealer_gamma < 0 ? 'gamma-neg' : 'gamma-pos';
                        return `
                            <div class="gamma-bar-wrapper" title="Strike: ${formatMoney(g.strike)}\nGamma: ${g.dealer_gamma.toFixed(4)}">
                                <div class="gamma-bar ${barClass}" style="height: ${barHeight}%;"></div>
                                <div class="gamma-label">${g.strike/1000}k</div>
                            </div>
                        `;
                    }).join('');

                    gammaChartHtml = `
                        <div class="gamma-chart-container">
                            <div class="spot-price-line" style="left: ${spotPositionPercent}%;"></div>
                            <div class="gamma-chart">${barsHtml}</div>
                        </div>
                    `;
                }

                // Hot Zone Table
                const hotZoneHtml = expiry.short_gamma_near_spot.map(z => `
                    <tr>
                        <td>${formatMoney(z.strike)}</td>
                        <td class="negative">${z.dealer_gamma.toFixed(4)}</td>
                    </tr>
                `).join('');

                expirationsHtml += `
                    <div class="expiry-card">
                        <div class="card-header">
                            <div class="card-header-title">
                                ${expiry.expiration_date} <small>(${expiry.day_of_week})</small>
                            </div>
                            <span class="oi-type-pill oi-type-${expiry.option_type.toLowerCase()}">${expiry.option_type}</span>
                        </div>
                        <div class="card-body">
                            <div class="stat-grid">
                                <div class="stat-grid-item">
                                    <div class="label">Notional Value</div>
                                    <div class="value">${formatMoney(expiry.notional_value_usd)}</div>
                                </div>
                                <div class="stat-grid-item">
                                    <div class="label">Max Pain</div>
                                    <div class="value">${expiry.max_pain_strike ? formatMoney(expiry.max_pain_strike) : 'N/A'}</div>
                                </div>
                                <div class="stat-grid-item">
                                    <div class="label">24h Volume</div>
                                    <div class="value">${formatNum(expiry.total_volume_24h_btc, 1)} BTC</div>
                                </div>
                                <div class="stat-grid-item">
                                    <div class="label">IV Skew (C-P)</div>
                                    ${formatSkew(expiry.average_iv_data.skew_proxy)}
                                </div>
                            </div>
                            <div class="oi-walls-container">
                                <div class="oi-wall-column calls">
                                    <h4>Call OI Walls (Resistance)</h4>
                                    <div class="oi-wall-list">${callsHtml}</div>
                                </div>
                                <div class="oi-wall-column puts">
                                    <h4>Put OI Walls (Support)</h4>
                                    <div class="oi-wall-list">${putsHtml}</div>
                                </div>
                            </div>
                            <div class="gamma-section">
                                <div class="gamma-profile">
                                    <h4>Dealer Gamma Profile (GEX)</h4>
                                    ${gammaChartHtml}
                                </div>
                                <div class="gamma-hot-zone">
                                    <h4>Volatility Hot Zone</h4>
                                    <div class="table-wrapper">
                                        <table class="hot-zone-table">
                                            <thead><tr><th>Strike</th><th>Gamma</th></tr></thead>
                                            <tbody>${hotZoneHtml}</tbody>
                                        </table>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            }
    
            container.innerHTML = `<div class="options-container">${headerStatsHtml}${expirationsHtml}</div>`;
    
        } catch (error) {
            console.error("Could not fetch or render options data:", error);
            container.innerHTML = `<p style="text-align: center; padding: 40px; color: var(--red-text);">Error loading options data. Please check the console.</p>`;
        }
    }

    // --- HISTORY TOGGLE LOGIC ---
    function updateToggleButtonsVisibility() {
        const tradesBody = document.getElementById('completed-trades-tbody');
        const tradesButton = document.getElementById('toggle-old-trades');
        if (tradesBody && tradesButton) {
            tradesButton.style.display = tradesBody.querySelector('.historical-entry') ? 'block' : 'none';
        }
        const setupsContainer = document.getElementById('setups-image-container');
        const setupsButton = document.getElementById('toggle-old-setups-images');
         if (setupsContainer && setupsButton) {
            setupsButton.style.display = setupsContainer.querySelector('.historical-entry') ? 'block' : 'none';
        }
    }

    function toggleHistoricalRows(tbodyId, button) {
        const tbody = document.getElementById(tbodyId);
        if (!tbody) return;
        const historicalRows = tbody.querySelectorAll('.historical-entry');
        if (historicalRows.length === 0) return;
        const isCurrentlyHidden = historicalRows[0].style.display === 'none';
        const displayStyle = isCurrentlyHidden ? 'table-row' : 'none';
        historicalRows.forEach(row => { row.style.display = displayStyle; });
        button.textContent = isCurrentlyHidden ? 'Hide Older' : 'Show All';
        adjustCollapsibleSize(button);
    }
    
    function toggleHistoricalImages(containerId, button) {
        const container = document.getElementById(containerId);
        if (!container) return;
        const historicalImages = container.querySelectorAll('.historical-entry');
        if (historicalImages.length === 0) return;
        const isCurrentlyHidden = historicalImages[0].style.display === 'none';
        const displayStyle = isCurrentlyHidden ? 'flex' : 'none';
        historicalImages.forEach(img => { img.style.display = displayStyle; });
        button.textContent = isCurrentlyHidden ? 'Hide Older' : 'Show All';
        adjustCollapsibleSize(button);
    }


    // --- RENDERING FUNCTIONS ---
    function renderNotes(notesData) {
        const container = DOM.notesContainer;
        if (!container) return;

        const sortedIds = Object.keys(notesData).sort((a, b) => (notesData[b].timestamp || 0) - (notesData[a].timestamp || 0));

        const notesHtml = sortedIds.map(id => {
            const note = notesData[id];
            const masterDeleteBtn = STATE.isMasterUser 
                ? `<button class="note-delete-btn" data-note-id="${id}" title="Delete Note">&times;</button>` 
                : '';
            
            return `
                <div class="note-item" id="note-item-${id}">
                    <div class="note-item-header" data-note-id="${id}">
                        ${masterDeleteBtn}
                        <div class="note-icon">📝</div>
                        <h4 class="note-title">${note.title || 'Untitled Note'}</h4>
                    </div>
                </div>
            `;
        }).join('');

        container.innerHTML = notesHtml;
        adjustCollapsibleSize(container);
    }

    function renderMarketOpens() {
        const data = STATE.marketOpens;
        if (!data?.opens) return;
    
        const btcData = data.opens['BTC-USDT'];
        if (btcData) {
            DOM.btcDailyOpen.textContent = formatCurrency(btcData.daily);
            DOM.btcWeeklyOpen.textContent = formatCurrency(btcData.weekly);
            DOM.btcMonthlyOpen.textContent = formatCurrency(btcData.monthly);
        }
    
        const ethData = data.opens['ETH-USDT'];
        if (ethData) {
            DOM.ethDailyOpen.textContent = formatCurrency(ethData.daily);
            DOM.ethWeeklyOpen.textContent = formatCurrency(ethData.weekly);
            DOM.ethMonthlyOpen.textContent = formatCurrency(ethData.monthly);
        }
    
        if (data.last_updated) {
            const lastUpdatedDate = new Date(data.last_updated);
            DOM.keyOpensLastUpdated.textContent = lastUpdatedDate.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
            
            const now = new Date();
            const todayUTCStart = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));
            
            const lastUpdatedContainer = DOM.keyOpensLastUpdated.parentElement;
    
            if (lastUpdatedDate.getTime() >= todayUTCStart.getTime()) {
                lastUpdatedContainer.classList.add('updated-today');
                DOM.btcDailyOpen.classList.add('updated-today-value');
                DOM.ethDailyOpen.classList.add('updated-today-value');
            } else {
                lastUpdatedContainer.classList.remove('updated-today');
                DOM.btcDailyOpen.classList.remove('updated-today-value');
                DOM.ethDailyOpen.classList.remove('updated-today-value');
            }
        }
    }

    function renderCrossoverSignals(signalData) {
        const ethContainer = document.getElementById('eth-crossover-signal-container');
        const btcContainer = document.getElementById('btc-crossover-signal-container');
        if (!ethContainer || !btcContainer) return;

        let ethHtml = '';
        let btcHtml = '';

        const symbols = Object.keys(signalData).sort();

        for (const symbol of symbols) {
            if (Object.hasOwnProperty.call(signalData, symbol)) {
                const tableHtml = createCrossoverSignalTableHTML(symbol, signalData[symbol]);
                if (symbol.startsWith('ETH')) {
                    ethHtml += tableHtml;
                } else if (symbol.startsWith('BTC')) {
                    btcHtml += tableHtml;
                }
            }
        }
        ethContainer.innerHTML = ethHtml;
        btcContainer.innerHTML = btcHtml;
        
        const lastUpdatedEl = document.getElementById('crossover-signals-last-updated');
        if(lastUpdatedEl) lastUpdatedEl.textContent = `Last Updated: ${new Date().toLocaleString()}`;
        
        adjustCollapsibleSize(ethContainer);
        adjustCollapsibleSize(btcContainer);
    }

    function createCrossoverSignalTableHTML(symbol, symbolData) {
        const timeframes = ['1h', '2h', '4h', '1d', '1w', '1M'];
        const tableRows = timeframes.map(tf => {
            const data = symbolData[tf] || { stage: 'N/A', colour: 'Grey', Level: 'N/A' };
            
            let colorClass = 'signal-cell-grey'; 
            if (data.colour === 'Green') colorClass = 'signal-cell-green'; 
            else if (data.colour === 'Red') colorClass = 'signal-cell-red';

            const levelValue = data['0-Candle Support'] || data['0-Candle Resistance'] || data['Level'] || 'N/A';

            return `<tr>
                        <td>${tf.toUpperCase()}</td>
                        <td class="signal-cell ${colorClass}">${data.stage}</td>
                        <td class="support-value">${levelValue}</td>
                    </tr>`;
        }).join('');

        return `<div class="crossover-signals-table-wrapper">
                    <h3>${symbol.replace('USDT', '/USDT')} Crossover Signal</h3>
                    <div class="table-wrapper">
                        <table class="crossover-signals-table">
                            <thead>
                                <tr>
                                    <th>Timeframe</th>
                                    <th>Signal Stage</th>
                                    <th>0candle Resistance</th>
                                </tr>
                            </thead>
                            <tbody>${tableRows}</tbody>
                        </table>
                    </div>
                </div>`;
    }
        function renderAttachmentThumbnails(entry, entryId, entryType) {
            const images = entry.attachedImages || {};
            const masterDeleteBtn = (imageId, fileName) => (STATE.isMasterUser) ? `<button class="delete-trade-image" title="Delete Attachment" data-entry-id="${entryId}" data-entry-type="${entryType}" data-image-id="${imageId}" data-filename="${fileName}">×</button>` : '';
            const thumbnailsHtml = Object.keys(images).sort((a, b) => images[b].timestamp - images[a].timestamp).map(imageId => {
                const imgData = images[imageId];
                if (!imgData?.url) return '';
                return `<div class="thumbnail-wrapper">${masterDeleteBtn(imageId, imgData.fileName)}<img src="${imgData.url}" alt="Attachment" data-full-src="${imgData.url}" data-caption="Attachment for ${entryType} ${entryId}"></div>`;
            }).join('');
            return `<td class="trade-image-thumbnails">${thumbnailsHtml}</td>`;
        }
        
        function renderSentimentReceipts() {
            const tbody = DOM.sentimentReceiptsTbody;
            if (!tbody) return;
        
            const receipts = STATE.allSentimentReceipts || {};
            const receiptIds = Object.keys(receipts).sort().reverse();
            const currentViewerId = getViewerId();
            const perthTodayStr = getPerthDateString();
        
            let rowsHtml = '';
            const paginationControls = document.getElementById('sentiment-pagination-controls');
            const showAllButton = document.getElementById('toggle-all-sentiments');
        
            if (STATE.sentimentShowAll) {
                const totalItems = receiptIds.length;
                const totalPages = Math.ceil(totalItems / STATE.sentimentItemsPerPage);
                if (STATE.sentimentCurrentPage > totalPages && totalPages > 0) STATE.sentimentCurrentPage = totalPages;
                if (STATE.sentimentCurrentPage < 1) STATE.sentimentCurrentPage = 1;
        
                const startIndex = (STATE.sentimentCurrentPage - 1) * STATE.sentimentItemsPerPage;
                const endIndex = startIndex + STATE.sentimentItemsPerPage;
                const pageReceiptIds = receiptIds.slice(startIndex, endIndex);
        
                rowsHtml = pageReceiptIds.map(id => {
                    const receipt = receipts[id];
                    let sentimentColor = 'var(--text-color)';
                    if (receipt.sentiment === 'long') sentimentColor = 'var(--green-text)';
                    if (receipt.sentiment === 'short') sentimentColor = 'var(--red-text)';
                    const ownerActionsHtml = (receipt.viewerId === currentViewerId && STATE.isMasterUser) ? `<button class="attach-image-btn" data-id="${id}" data-type="sentiment" title="Attach Picture" style="background-color: #17a2b8;">Pic</button><button class="edit-sentiment-note-btn" data-id="${id}">Note</button><button class="delete-sentiment-btn" data-id="${id}" title="Delete Entry">×</button>` : '';
                    const displayTimestamp = typeof receipt.timestamp === 'number' ? new Date(receipt.timestamp).toLocaleString() : (receipt.timestamp || '--');
                    return `<tr><td>${receipt.asset || '--'}</td><td style="color: ${sentimentColor};">${receipt.sentiment || '--'}</td><td class="sentiment-note-cell">${receipt.note || ''}</td>${renderAttachmentThumbnails(receipt, id, 'sentiment')}<td>${displayTimestamp}</td><td class="action-buttons">${ownerActionsHtml}</td></tr>`;
                }).join('');
        
                showAllButton.style.display = 'none';
                if (totalPages > 1) {
                    paginationControls.style.display = 'flex';
                    document.getElementById('sentiment-page-info').textContent = `Page ${STATE.sentimentCurrentPage} of ${totalPages}`;
                    document.getElementById('sentiment-prev-page').disabled = (STATE.sentimentCurrentPage === 1);
                    document.getElementById('sentiment-next-page').disabled = (STATE.sentimentCurrentPage === totalPages);
                } else {
                    paginationControls.style.display = 'none';
                }
        
            } else {
                let hasHistorical = false;
                rowsHtml = receiptIds.map(id => {
                    const receipt = receipts[id];
                    const receiptPerthDateStr = (typeof receipt.timestamp === 'number') ? getPerthDateString(new Date(receipt.timestamp)) : '';
                    const isHistorical = (receiptPerthDateStr !== perthTodayStr);
                    if(isHistorical) hasHistorical = true;
        
                    let sentimentColor = 'var(--text-color)';
                    if (receipt.sentiment === 'long') sentimentColor = 'var(--green-text)';
                    if (receipt.sentiment === 'short') sentimentColor = 'var(--red-text)';
                    const ownerActionsHtml = (receipt.viewerId === currentViewerId && STATE.isMasterUser) ? `<button class="attach-image-btn" data-id="${id}" data-type="sentiment" title="Attach Picture" style="background-color: #17a2b8;">Pic</button><button class="edit-sentiment-note-btn" data-id="${id}">Note</button><button class="delete-sentiment-btn" data-id="${id}" title="Delete Entry">×</button>` : '';
                    const displayTimestamp = typeof receipt.timestamp === 'number' ? new Date(receipt.timestamp).toLocaleString() : (receipt.timestamp || '--');
                    return `<tr class="${isHistorical ? 'historical-entry' : ''}"><td>${receipt.asset || '--'}</td><td style="color: ${sentimentColor};">${receipt.sentiment || '--'}</td><td class="sentiment-note-cell">${receipt.note || ''}</td>${renderAttachmentThumbnails(receipt, id, 'sentiment')}<td>${displayTimestamp}</td><td class="action-buttons">${ownerActionsHtml}</td></tr>`;
                }).join('');
        
                paginationControls.style.display = 'none';
                showAllButton.style.display = hasHistorical ? 'block' : 'none';
            }
        
            tbody.innerHTML = rowsHtml;
            adjustCollapsibleSize(tbody);
        }

        function renderLiveTable(data) {
            const trades = data || {};
            const masterButtonsHtml = (id) => STATE.isMasterUser ? `<td class="action-buttons"><button class="attach-image-btn" data-id="${id}" data-type="live" title="Attach Picture" style="background-color: #17a2b8;">Pic</button><button class="add-to-position-btn" data-id="${id}" title="Add to Position" style="background-color: #28a745;">+</button><button class="win-btn" data-id="${id}">Win</button><button class="loss-btn" data-id="${id}">Loss</button><button class="note-btn" data-id="${id}">Edit</button><button class="delete-btn" data-id="${id}">Delete</button></td>` : '';
            const masterEditableCell = (className, field, tradeId, value, isMaster, digits = 2) => {
                const formattedValue = (typeof value === 'number') ? value.toFixed(digits) : value;
                return isMaster ? `<td class="${className}" data-id="${tradeId}" data-field="${field}" contenteditable="true" title="Click to edit">${formattedValue}</td>` : `<td>${formattedValue}</td>`;
            };
            const rowsHtml = Object.keys(trades).sort((a, b) => new Date(trades[b].date) - new Date(trades[a].date)).map(id => {
                const trade = trades[id];
                const profitString = `$${parseFloat(trade.expected_profit || 0).toFixed(2)} (${parseFloat(trade.expected_profit_percent || 0).toFixed(2)}%)`;
                const lossString = `$${parseFloat(trade.expected_loss || 0).toFixed(2)} (${parseFloat(trade.expected_loss_percent || 0).toFixed(2)}%)`;
                
                let rrString;
                if (trade.rr && !isNaN(parseFloat(trade.rr))) {
                    rrString = `${parseFloat(trade.rr).toFixed(2)}:1`;
                } else {
                    const metrics = calculateTradeMetrics(trade);
                    rrString = metrics.rr > 0 ? `${parseFloat(metrics.rr).toFixed(2)}:1` : '--';
                }

                const entriesList = (trade.entry_prices || [trade.entry]).join(', ');
                return `<tr><td>${trade.symbol}</td><td>${trade.type}</td>${masterEditableCell('editable-cell', 'entry', id, trade.entry, STATE.isMasterUser, 4)}${masterEditableCell('note-cell editable-cell', 'entry_prices', id, entriesList, STATE.isMasterUser)}${masterEditableCell('editable-cell', 'stoploss', id, trade.stoploss, STATE.isMasterUser, 4)}${masterEditableCell('editable-cell', 'target', id, trade.target, STATE.isMasterUser, 4)}${masterEditableCell('editable-cell', 'size', id, trade.size, STATE.isMasterUser, 2)}<td>${parseFloat(trade.estimated_total_fee || 0).toFixed(2)}</td><td style="color: #28a745;">${profitString}</td><td style="color: #dc3545;">${lossString}</td><td>${rrString}</td><td>${trade.date ? new Date(trade.date).toLocaleString() : '--'}</td><td class="note-cell" title="${trade.note || ''}">${trade.note || ''}</td>${renderAttachmentThumbnails(trade, id, 'live')}${masterButtonsHtml(id)}</tr>`;
            }).join('');
            DOM.tradesTbody.innerHTML = rowsHtml;
            adjustCollapsibleSize(DOM.tradesTbody);
        }

        function renderCompletedTable(data) {
            const trades = data || {};
            const perthTodayStr = getPerthDateString();
            
            const masterButtonsHtml = (id) => STATE.isMasterUser ? `<td class="action-buttons"><button class="attach-image-btn" data-id="${id}" data-type="completed" title="Attach Picture" style="background-color: #17a2b8;">Pic</button><button class="merge-btn-completed" data-id="${id}" title="Merge another trade into this one" style="background-color: #ffc107; color: #333;">Merge</button><button class="note-btn-completed" data-id="${id}">Edit</button><button class="delete-btn-completed" data-id="${id}">Delete</button></td>` : '';
            
            const rowsHtml = Object.keys(trades).sort((a, b) => new Date(trades[b].closed_date) - new Date(trades[a].closed_date)).map(id => {
                const trade = trades[id];
                const resultColor = trade.net_result >= 0 ? 'var(--green-text)' : 'var(--red-text)';
                const totalFees = (trade.entry_fee || 0) + (trade.exit_fee || 0);
                const entriesList = (trade.entry_prices || [trade.entry]).join(', ');

                let rrString;
                if (trade.rr && !isNaN(parseFloat(trade.rr))) {
                    rrString = `${parseFloat(trade.rr).toFixed(2)}:1`;
                } else {
                    const metrics = calculateTradeMetrics(trade);
                    rrString = metrics.rr > 0 ? `${parseFloat(metrics.rr).toFixed(2)}:1` : '--';
                }
                
                let closedPerthDateStr = '', isHistorical;
                if (trade.closed_date) {
                    const closedDate = new Date(trade.closed_date);
                    closedPerthDateStr = getPerthDateString(closedDate);
                    isHistorical = (closedPerthDateStr !== perthTodayStr);
                } else { 
                    isHistorical = true; 
                }
                return `<tr class="${isHistorical ? 'historical-entry' : ''}" style="${isHistorical ? 'display: none;' : ''}" data-date="${closedPerthDateStr}"><td>${trade.symbol}</td><td>${trade.type}</td><td>${parseFloat(trade.entry).toFixed(4)}</td><td class="note-cell">${entriesList}</td><td>${parseFloat(trade.stoploss || 0).toFixed(4)}</td><td>${parseFloat(trade.target || 0).toFixed(2)}</td><td>${parseFloat(trade.size || 0).toFixed(2)}</td><td style="color: var(--green-text);">${formatCurrency(trade.expected_profit)}</td><td style="color: var(--red-text);">${formatCurrency(trade.expected_loss)}</td><td>${rrString}</td><td>${parseFloat(trade.exit_price).toFixed(2)}</td><td>${totalFees.toFixed(2)}</td><td style="color:${resultColor};font-weight:bold;">${parseFloat(trade.net_result).toFixed(2)}</td><td>${trade.date ? new Date(trade.date).toLocaleString() : '--'}</td><td>${trade.closed_date ? new Date(trade.closed_date).toLocaleString() : '--'}</td><td class="note-cell" title="${trade.note || ''}">${trade.note || ''}</td>${renderAttachmentThumbnails(trade, id, 'completed')}${masterButtonsHtml(id)}</tr>`;
            }).join('');
            DOM.completedTradesTbody.innerHTML = rowsHtml;

            updateToggleButtonsVisibility();
            adjustCollapsibleSize(DOM.completedTradesTbody);
        }

        function renderGenericImageLibrary(imagesData, containerElement, libraryType) {
            const images = imagesData || {};
            if (!containerElement) return;
            const perthTodayStr = getPerthDateString();

            const masterButtonsHtml = (id, fileName) => (STATE.isMasterUser) ? `<button class="delete-library-image" title="Delete Image" data-id="${id}" data-filename="${fileName}" data-library-type="${libraryType}"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><path d="M135.2 17.7L128 32H32C14.3 32 0 46.3 0 64s14.3 32 32 32h384c17.7 0 32-14.3 32-32s-14.3-32-32-32h-96l-7.2-14.3C307.4 6.8 296.3 0 284.2 0H163.8c-12.1 0-23.2 6.8-28.6 17.7zM416 128H32l21.2 339c1.6 25.3 22.6 45 47.9 45h245.8c25.3 0 46.3-19.7 47.9-45L416 128z"/></svg></button><button class="edit-caption-btn" title="Edit Caption" data-id="${id}" data-library-type="${libraryType}"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><path d="M471.6 21.7c-21.9-21.9-57.3-21.9-79.2 0L362.3 51.7l97.9 97.9 30.1-30.1c21.9-21.9 21.9-57.3 0-79.2L471.6 21.7zm-299.2 220c-6.1 6.1-10.8 13.6-13.5 21.9l-29.6 88.8c-2.9 8.6-.6 18.1 5.8 24.6s15.9 8.7 24.6 5.8l88.8-29.6c8.2-2.7 15.7-7.4 21.9-13.5L437.7 172.3 339.7 74.3 172.4 241.7zM96 64C43 64 0 107 0 160V416c0 53 43 96 96 96H352c53 0 96-43 96-96V320c0-17.7-14.3-32-32-32s-32 14.3-32 32v96c0 17.7-14.3 32-32 32H96c-17.7 0-32-14.3-32-32V160c0-17.7 14.3-32 32-32h96c17.7 0 32-14.3 32-32s-14.3-32-32-32H96z"/></svg></button>` : '';
            
            const imagesHtml = Object.keys(images).sort((a, b) => images[b].timestamp - images[a].timestamp).map(id => {
                const imgData = images[id]; if (!imgData?.url) return '';
                const caption = imgData.caption || (imgData.timestamp ? new Date(imgData.timestamp).toLocaleString() : ' ');

                let wrapperClasses = 'library-image-wrapper';
                let wrapperStyle = '';

                if (libraryType === 'setups_images' && imgData.timestamp) {
                    const imagePerthDateStr = getPerthDateString(new Date(imgData.timestamp));
                    const isHistorical = imagePerthDateStr !== perthTodayStr;
                    if (isHistorical) {
                        wrapperClasses += ' historical-entry';
                        wrapperStyle = 'style="display: none;"';
                    }
                }
                
                return `<div class="${wrapperClasses}" ${wrapperStyle}>${masterButtonsHtml(id, imgData.fileName)}<img src="${imgData.url}" alt="${libraryType} Image" data-full-src="${imgData.url}" data-caption="${caption}"><div class="library-image-caption" title="${caption}">${caption}</div></div>`;
            }).join('');
            containerElement.innerHTML = imagesHtml;

            if (libraryType === 'setups_images') {
                updateToggleButtonsVisibility();
            }

            adjustCollapsibleSize(containerElement);
        }

        function renderChartLibrary2Folders() {
            if (!DOM.chartLibrary2Container) return;
            const foldersHtml = CL2_FOLDERS.map(folder => {
                const imageCount = STATE.chartLibrary2Data[folder] ? Object.keys(STATE.chartLibrary2Data[folder]).length : 0;
                return `<div class="cl2-folder-card" data-folder="${folder}"><div class="cl2-folder-icon">📁</div><h4>${folder}</h4><div class="cl2-folder-count">${imageCount} image${imageCount !== 1 ? 's' : ''}</div></div>`;
            }).join('');
            DOM.chartLibrary2Container.innerHTML = `<div class="cl2-folder-grid">${foldersHtml}</div>`;
            if (STATE.isMasterUser) {
                document.querySelectorAll('.cl2-folder-card').forEach(folderEl => {
                    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => folderEl.addEventListener(eventName, e => { e.preventDefault(); e.stopPropagation(); }));
                    ['dragenter', 'dragover'].forEach(eventName => folderEl.addEventListener(eventName, () => folderEl.classList.add('drag-over')));
                    folderEl.addEventListener('dragleave', () => folderEl.classList.remove('drag-over'));
                    folderEl.addEventListener('drop', e => {
                        folderEl.classList.remove('drag-over');
                        if (e.dataTransfer?.files.length > 0) handleChartLibrary2Upload(e.dataTransfer.files, folderEl.dataset.folder);
                    });
                });
            }
        }

        function renderFolderContents(folderName) {
            if (!DOM.chartLibrary2Container) return;
            const imagesForFolder = STATE.chartLibrary2Data[folderName] || {};
            const headerHtml = `<div class="cl2-image-view-header"><button class="cl2-back-button">← Back to Folders</button><h3 class="cl2-view-title">${folderName}</h3><span></span></div>`;
            const masterDeleteButtonHtml = (id, fileName) => (STATE.isMasterUser) ? `<button class="delete-library-image" title="Delete Image" data-folder="${folderName}" data-id="${id}" data-filename="${fileName}"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><path d="M135.2 17.7L128 32H32C14.3 32 0 46.3 0 64s14.3 32 32 32h384c17.7 0 32-14.3 32-32s-14.3-32-32-32h-96l-7.2-14.3C307.4 6.8 296.3 0 284.2 0H163.8c-12.1 0-23.2 6.8-28.6 17.7zM416 128H32l21.2 339c1.6 25.3 22.6 45 47.9 45h245.8c25.3 0 46.3-19.7 47.9-45L416 128z"/></svg></button>` : '';
            const imagesHtml = Object.keys(imagesForFolder).sort((a, b) => imagesForFolder[b].timestamp - imagesForFolder[a].timestamp).map(id => {
                const imgData = imagesForFolder[id]; if (!imgData?.url) return '';
                const timestamp = imgData.timestamp ? new Date(imgData.timestamp).toLocaleString() : '';
                return `<div class="library-image-wrapper">${masterDeleteButtonHtml(id, imgData.fileName)}<img src="${imgData.url}" alt="Image from ${folderName}" data-full-src="${imgData.url}" data-caption="${timestamp}"><div class="library-image-caption" title="${timestamp}">${timestamp}</div></div>`;
            }).join('');
            const gridHtml = `<div class="cl2-image-grid">${imagesHtml || '<p>No images in this folder. Drag and drop to add some!</p>'}</div>`;
            DOM.chartLibrary2Container.innerHTML = headerHtml + gridHtml;
        }

        function renderChartLibrary2Preview() {
            const container = DOM.chartLibrary2PreviewContainer; if (!container) return;
            let html = '';
            CL2_FOLDERS.forEach(folderName => {
                const imagesInFolder = STATE.chartLibrary2Data[folderName];
                if (!imagesInFolder || Object.keys(imagesInFolder).length === 0) return;
                const latestImage = Object.values(imagesInFolder).sort((a, b) => b.timestamp - a.timestamp)[0];
                if (latestImage) {
                    const timestamp = latestImage.timestamp ? new Date(latestImage.timestamp).toLocaleString() : '';
                    const isToday = latestImage.timestamp && (getYYYYMMDD(new Date(latestImage.timestamp)) === getYYYYMMDD(new Date()));
                    const captionClass = isToday ? 'library-image-caption is-today' : 'library-image-caption';
                    html += `<div class="cl2-preview-item"><h4>${folderName}</h4><div class="library-image-wrapper"><img src="${latestImage.url}" alt="Latest from ${folderName}" data-full-src="${latestImage.url}" data-caption="${timestamp}"><div class="${captionClass}" title="${timestamp}">${timestamp}</div></div></div>`;
                }
            });
            container.innerHTML = html;
        }

        function renderDateNavigation() {
            const safeSymbol = getSafeSymbol(DOM.journalSymbolEl.value);
            const timeframe = DOM.journalTimeframeEl.value;
            let buttonsHtml = '';
            for (let i = -2; i <= 2; i++) {
                const date = new Date(STATE.centerDate); date.setUTCDate(STATE.centerDate.getUTCDate() + i);
                const yyyymmdd = getYYYYMMDD(date);
                const isActive = yyyymmdd === getYYYYMMDD(STATE.selectedDate);
                const hasEntry = (STATE.journalText[safeSymbol]?.[yyyymmdd]?.[timeframe] || '').trim();
                const btnClasses = `date-nav-btn ${isActive ? 'active' : ''} ${hasEntry ? 'has-entry' : ''}`;
                const btnText = date.toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', timeZone: 'UTC' });
                buttonsHtml += `<button class="${btnClasses}" data-date="${yyyymmdd}">${btnText}</button>`;
            }
            DOM.dateButtonsContainer.innerHTML = buttonsHtml;
        }

        function updateJournalView() {
            const safeSymbol = getSafeSymbol(DOM.journalSymbolEl.value);
            const timeframe = DOM.journalTimeframeEl.value;
            const yyyymmdd = getYYYYMMDD(STATE.selectedDate);
            const favouriteText = (STATE.favouriteEntries[safeSymbol] || {})[timeframe];
            if (favouriteText) {
                DOM.favouritedEntryText.textContent = favouriteText;
                DOM.favouritedEntryContainer.style.display = 'block';
            } else { DOM.favouritedEntryContainer.style.display = 'none'; }
            const dailyText = (STATE.journalText[safeSymbol]?.[yyyymmdd]?.[timeframe]) || '';
            DOM.journalEntryEl.value = dailyText;
            DOM.persistentNotesEl.value = STATE.persistentNotes;
            setTimeout(() => { adjustCollapsibleSize(DOM.journalEntryEl); adjustCollapsibleSize(DOM.persistentNotesEl); }, 50);
            DOM.favouriteBtn.classList.toggle('active', favouriteText && dailyText.trim() === favouriteText);
            renderJournalImages(safeSymbol, timeframe, yyyymmdd);
            renderDateNavigation();
        }

        function renderJournalImages(symbol, timeframe, selectedYMD) {
            const imagesForTimeframe = STATE.journalImages[symbol]?.[timeframe] || {};
            const allImageKeys = Object.keys(imagesForTimeframe);
            const filterMode = DOM.journalImageFilterEl.value;
            const imageKeysToRender = (filterMode === 'today') ? allImageKeys.filter(key => getYYYYMMDD(new Date(imagesForTimeframe[key].timestamp)) === selectedYMD) : allImageKeys;
            if (imageKeysToRender.length === 0) { DOM.journalImagesContainer.innerHTML = ''; return; }
            const deleteButtonHtml = (id, fileName) => (STATE.isMasterUser) ? `<button class="delete-journal-image" title="Delete Image" data-safe-symbol="${symbol}" data-timeframe="${timeframe}" data-id="${id}" data-filename="${fileName}"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><path d="M135.2 17.7L128 32H32C14.3 32 0 46.3 0 64s14.3 32 32 32h384c17.7 0 32-14.3 32-32s-14.3-32-32-32h-96l-7.2-14.3C307.4 6.8 296.3 0 284.2 0H163.8c-12.1 0-23.2 6.8-28.6 17.7zM416 128H32l21.2 339c1.6 25.3 22.6 45 47.9 45h245.8c25.3 0 46.3-19.7 47.9-45L416 128z"/></svg></button>` : '';
            const imagesHtml = imageKeysToRender.sort((a, b) => imagesForTimeframe[b].timestamp - imagesForTimeframe[a].timestamp).map(id => {
                const imgData = imagesForTimeframe[id];
                if (!imgData?.url || !imgData?.fileName) return '';
                return `<div class="journal-image-wrapper">${deleteButtonHtml(id, imgData.fileName)}<img src="${imgData.url}" alt="Journal Image" data-full-src="${imgData.url}" data-caption="Journal Image"></div>`;
            }).join('');
            DOM.journalImagesContainer.innerHTML = imagesHtml;
        }

        function renderEmaSnapshot(safeSymbol) {
            const container = DOM.emaSnapshotContainer;
            if (!container || !STATE.emaData.data) return;
            const { TIMEFRAMES, PERIODS, SHORT_NAMES } = CONFIG.EMA_ANALYSIS;
            const symbolEmaData = STATE.emaData.data[safeSymbol] || {};
            const currentPrice = symbolEmaData['15min']?.price || 0;
            const lastUpdatedHtml = STATE.emaData.last_updated ? `<p class="ema-last-updated">Last Updated: <span>${new Date(STATE.emaData.last_updated).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}</span></p>` : '';
            const priceDisplayHtml = `<div class="ema-table-container"><div class="current-price-display" style="font-size: 14px; margin-bottom: 15px;">Current Price (15m): <span class="price-value">${currentPrice > 0 ? formatCurrency(currentPrice) : '--'}</span></div></div>`;
            
            let summaryTableHtml = '';
            if (currentPrice > 0) {
                const htfForSummary = ['daily', '4hour', '2hour', '1hour'];
                const levelsHtf = [];
                htfForSummary.forEach(tf => {
                    const tfData = symbolEmaData[tf];
                    if (tfData) {
                        PERIODS.forEach(period => ['EMA', 'SMA'].forEach(type => {
                            const val = tfData[`${type}_${period}`];
                            if (val !== undefined) {
                                levelsHtf.push({
                                    label: `${SHORT_NAMES[tf]} ${type} ${period}`,
                                    value: val,
                                    isSupport: val < currentPrice
                                });
                            }
                        }));
                    }
                });

                const supportsHtfAll = levelsHtf.filter(l => l.isSupport).sort((a, b) => b.value - a.value);
                const resistancesHtfAll = levelsHtf.filter(l => !l.isSupport).sort((a, b) => a.value - b.value);
                
                let tableRowsHtml = '';
                supportsHtfAll.forEach(supHtf => {
                    tableRowsHtml += `<tr><td style="color: var(--text-color);">${supHtf.label}</td><td style="color: var(--green-text);">${Math.round(supHtf.value).toLocaleString()}</td></tr>`;
                });

                if (supportsHtfAll.length > 0 && resistancesHtfAll.length > 0) {
                     tableRowsHtml += '<tr class="separator-row"><td colspan="2"></td></tr>';
                }

                resistancesHtfAll.forEach(resHtf => {
                    tableRowsHtml += `<tr><td style="color: var(--text-color);">${resHtf.label}</td><td style="color: var(--red-text);">${Math.round(resHtf.value).toLocaleString()}</td></tr>`;
                });

                summaryTableHtml = `<div class="ema-summary-container"><div class="table-wrapper"><table class="ema-table" style="font-size: 11px; margin-top:0;"><thead><tr><th colspan="2">Major S/R (D, 4H, 2H, 1H)</th></tr><tr><th>Level</th><th>Value</th></tr></thead><tbody>${tableRowsHtml}</tbody></table></div></div>`;
            }
            
            const tableRowsHtml = TIMEFRAMES.map(tf => {
                const tfData = symbolEmaData[tf];
                const cellsHtml = PERIODS.flatMap(period => ['EMA', 'SMA'].map(type => { const value = tfData?.[`${type}_${period}`]; return (value !== undefined) ? `<td class="${currentPrice > 0 ? (value > currentPrice ? 'price-above' : 'price-below') : ''}">${Math.round(value).toLocaleString()}</td>` : '<td>...</td>'; })).join('');
                return `<tr><td>${SHORT_NAMES[tf] || tf}</td>${cellsHtml}</tr>`;
            }).join('');
            
            const tableHtml = `<div class="table-wrapper"><table class="ema-table"><thead><tr><th>TF</th>${PERIODS.flatMap(p => [`<th>EMA ${p}</th>`, `<th>SMA ${p}</th>`]).join('')}</tr></thead><tbody>${tableRowsHtml}</tbody></table></div>`;
            container.innerHTML = lastUpdatedHtml + priceDisplayHtml + summaryTableHtml + tableHtml;
        }


        function calculateAndDisplayPercentages(row) {
            if (!row) return;
            const cells = row.querySelectorAll('td');
            if (cells.length === 0) return;

            const setups = [
                { entry: 0, target: 1, targetPct: 2, stoploss: 3, stoplossPct: 4 },
                { entry: 5, target: 6, targetPct: 7, stoploss: 8, stoplossPct: 9 },
                { entry: 10, target: 11, targetPct: 12, stoploss: 13, stoplossPct: 14 }
            ];

            setups.forEach(setup => {
                const entryVal = parseFloat(cells[setup.entry].textContent.replace(/,/g, ''));
                const targetVal = parseFloat(cells[setup.target].textContent.replace(/,/g, ''));
                const stoplossVal = parseFloat(cells[setup.stoploss].textContent.replace(/,/g, ''));

                const targetPctCell = cells[setup.targetPct];
                const stoplossPctCell = cells[setup.stoplossPct];

                if (!isNaN(entryVal) && !isNaN(targetVal) && entryVal !== 0) {
                    const percent = ((targetVal - entryVal) / entryVal) * 100;
                    targetPctCell.textContent = percent.toFixed(1) + '%';
                    targetPctCell.style.color = percent >= 0 ? 'var(--green-text)' : 'var(--red-text)';
                } else {
                    targetPctCell.textContent = '';
                }

                if (!isNaN(entryVal) && !isNaN(stoplossVal) && entryVal !== 0) {
                    const percent = ((stoplossVal - entryVal) / entryVal) * 100;
                    stoplossPctCell.textContent = percent.toFixed(1) + '%';
                    stoplossPctCell.style.color = percent >= 0 ? 'var(--green-text)' : 'var(--red-text)';
                } else {
                    stoplossPctCell.textContent = '';
                }
            });
        }

        function applyHighlightingToSetupsTable(tableElement) {
            if (!tableElement) return;
            const tbody = tableElement.querySelector('tbody');
            const letterCheckRegex = /[a-zA-Z]/; 
            const setupTypes = [ { baseIndex: 0 }, { baseIndex: 5 }, { baseIndex: 10 } ];
            tbody.querySelectorAll('tr').forEach(row => {
                const cells = row.querySelectorAll('td'); if (cells.length === 0) return;
                setupTypes.forEach(setup => {
                    const [entryCell, targetCell, stoplossCell] = [cells[setup.baseIndex], cells[setup.baseIndex + 1], cells[setup.baseIndex + 3]];
                    [entryCell, targetCell, stoplossCell].forEach(cell => cell.classList.remove('highlight-long', 'highlight-short'));
                    const entryText = entryCell.textContent.trim(), targetText = targetCell.textContent.trim();
                    if (letterCheckRegex.test(entryText) || letterCheckRegex.test(targetText)) return; 
                    const entryValue = parseFloat(String(entryText).replace(/,/g, '')), targetValue = parseFloat(String(targetText).replace(/,/g, ''));
                    if (isNaN(entryValue) || isNaN(targetValue)) return;
                    if (targetValue > entryValue) [entryCell, targetCell, stoplossCell].forEach(cell => cell.classList.add('highlight-long'));
                    else if (entryValue > targetValue) [entryCell, targetCell, stoplossCell].forEach(cell => cell.classList.add('highlight-short'));
                });
            });
        }
        
        function renderSetupsTable(tableElement, data, notesTextareaId) {
            if (!tableElement) return;
            const tbody = tableElement.querySelector('tbody');
            tbody.querySelectorAll('tr').forEach(row => {
                const timeframe = row.firstElementChild.textContent.trim();
                const rowData = data[timeframe] || {};
                const cells = row.querySelectorAll('td');
                cells[0].textContent = rowData.zero_entry || ''; cells[1].textContent = rowData.zero_target || ''; cells[3].textContent = rowData.zero_stoploss || '';
                cells[5].textContent = rowData.four_entry || ''; cells[6].textContent = rowData.four_target || ''; cells[8].textContent = rowData.four_stoploss || '';
                cells[10].textContent = rowData.bounce_entry || ''; cells[11].textContent = rowData.bounce_target || ''; cells[13].textContent = rowData.bounce_stoploss || '';
                
                calculateAndDisplayPercentages(row);
            });
            const notesTextarea = document.getElementById(notesTextareaId);
            if (notesTextarea) { 
                notesTextarea.value = data.global_notes || ''; 
                adjustCollapsibleSize(notesTextarea);
            }
            applyHighlightingToSetupsTable(tableElement);
            adjustCollapsibleSize(tableElement);
        }
        
        function renderSrSummaryTable(symbol) {
            const summaryTbody = document.getElementById('sr-summary-tbody');
            const summaryContainer = document.getElementById('sr-summary-zones-container');
            if (!summaryTbody || !summaryContainer) return;

            const symbolData = STATE.srData.data?.[symbol];
            if (!symbolData || Object.keys(STATE.srData.data).length === 0) {
                summaryContainer.style.display = 'none';
                return;
            }

            const lookbackOptions = Array.from(document.getElementById('sr-lookback').options);
            const lookbacks = lookbackOptions.map(opt => ({ value: opt.value, text: opt.text }));

            let rowsHtml = '';
            lookbacks.forEach(lookback => {
                const lookbackData = symbolData[lookback.value] || {};
                const supportLevels = lookbackData.support || [];
                const resistanceLevels = lookbackData.resistance || [];

                const topSupport = supportLevels.length > 0 ? supportLevels[0] : null;
                const supportZoneText = topSupport 
                    ? `${Math.round(topSupport['Price Start'])} - ${Math.round(topSupport['Price End'])}`
                    : '--';
                
                const topResistance = resistanceLevels.length > 0 ? resistanceLevels[0] : null;
                const resistanceZoneText = topResistance
                    ? `${Math.round(topResistance['Price Start'])} - ${Math.round(topResistance['Price End'])}`
                    : '--';

                rowsHtml += `
                    <tr>
                        <td style="text-align: left; padding-left: 15px; font-weight: 500;">${lookback.text}</td>
                        <td class="sr-center-price" style="color: var(--green-text);">${supportZoneText}</td>
                        <td class="sr-center-price" style="color: var(--red-text);">${resistanceZoneText}</td>
                    </tr>
                `;
            });
            
            summaryTbody.innerHTML = rowsHtml;
            summaryContainer.style.display = 'block';
        }

        function renderSrLevels() {
            const selectedSymbol = getSafeSymbol(DOM.srSymbolEl.value);
            const selectedLookback = DOM.srLookbackEl.value;
            
            renderSrSummaryTable(selectedSymbol);

            const lookbackData = STATE.srData.data?.[selectedSymbol]?.[selectedLookback] || {};
            const analysisParams = lookbackData.analysis_params || {};

            DOM.srLastUpdatedTime.textContent = STATE.srData.last_updated 
                ? new Date(STATE.srData.last_updated).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }) 
                : '--';
                
            DOM.srMetadataTimeframes.textContent = (analysisParams.timeframes_analyzed || []).join(', ') || '--';
            DOM.srMetadataWindows.textContent = '5, 8, 13, 21, 34'; 

            if (analysisParams.lookback_days) {
                const atrText = analysisParams.atr_percent ? ` / ATR: ${(analysisParams.atr_percent * 100).toFixed(2)}%` : '';
                DOM.srMetadataDates.textContent = `${analysisParams.lookback_days} Days${atrText}`;
            } else {
                DOM.srMetadataDates.textContent = '--';
            }

            const supportLevels = lookbackData.support || [];
            const resistanceLevels = lookbackData.resistance || [];
            
            const allScores = [...supportLevels, ...resistanceLevels].map(l => l['Strength Score']);
            const maxScore = allScores.length > 0 ? Math.max(...allScores) : 1;

            const buildLevelRow = (level, type) => {
                const priceStart = level['Price Start'] !== undefined ? Math.round(level['Price Start']) : 'N/A';
                const priceEnd = level['Price End'] !== undefined ? Math.round(level['Price End']) : 'N/A';
                const centerPrice = level['Center Price'] !== undefined ? Math.round(level['Center Price']) : 'N/A';
                const score = level['Strength Score'] || 0;
                const scoreWidth = (score / maxScore) * 100;
                const barColor = type === 'support' ? 'var(--green-bar)' : 'var(--red-bar)';
                
                return `
                    <tr>
                        <td>${priceStart} - ${priceEnd}</td>
                        <td class="sr-center-price">${centerPrice}</td>
                        <td class="sr-score-cell" style="background-image: linear-gradient(to right, ${barColor} ${scoreWidth}%, transparent ${scoreWidth}%);"><span class="sr-score-value">${Math.round(score)}</span></td>
                        <td class="sr-pivots-cell">${level['Pivot Count']}</td>
                    </tr>`;
            };

            DOM.supportLevelsTbody.innerHTML = supportLevels.map(level => buildLevelRow(level, 'support')).join('');
            DOM.resistanceLevelsTbody.innerHTML = resistanceLevels.map(level => buildLevelRow(level, 'resistance')).join('');
        }

        function renderLevelNotes(notesData) {
            STATE.levelNotes = notesData || {};
            for (const safeSymbol in STATE.levelNotes) {
                if (Object.hasOwnProperty.call(STATE.levelNotes, safeSymbol)) {
                    const symbolNotes = STATE.levelNotes[safeSymbol];
                    const symbolPrefix = safeSymbol.split('-')[0].toLowerCase();
                    for (const timeframe in symbolNotes) {
                        if (Object.hasOwnProperty.call(symbolNotes, timeframe)) {
                            const note = symbolNotes[timeframe];
                            const textareaEl = document.getElementById(`${symbolPrefix}-${timeframe}-note`);
                            if (textareaEl) {
                                textareaEl.value = note;
                                adjustCollapsibleSize(textareaEl);
                            }
                        }
                    }
                }
            }
        }
        
        // --- DATA HANDLING AND SAVING ---
        const saveLevelNotes = (inputElement) => {
            if (!STATE.isMasterUser) return;
            clearTimeout(STATE.levelNotesSaveTimer);
            STATE.levelNotesSaveTimer = setTimeout(() => {
                const idParts = inputElement.id.split('-');
                const symbol = `${idParts[0].toUpperCase()}-USDT`;
                const timeframe = idParts[1];
                const value = inputElement.value;

                dbRefs.levelNotes.child(getSafeSymbol(symbol)).child(timeframe).set(value)
                    .catch(e => console.error("Error saving level note:", e));
            }, 750);
        };
        
        function saveSetupsTable(tableElement, dbRef, statusElement, notesTextareaId) {
            if (!STATE.isMasterUser) return;
            const dataToSave = {};
            const tbody = tableElement.querySelector('tbody');
            tbody.querySelectorAll('tr').forEach(row => {
                const timeframe = row.firstElementChild.textContent.trim();
                const cells = row.querySelectorAll('td');
                dataToSave[timeframe] = {
                    zero_entry: cells[0].textContent.trim(), zero_target: cells[1].textContent.trim(), zero_stoploss: cells[3].textContent.trim(),
                    four_entry: cells[5].textContent.trim(), four_target: cells[6].textContent.trim(), four_stoploss: cells[8].textContent.trim(),
                    bounce_entry: cells[10].textContent.trim(), bounce_target: cells[11].textContent.trim(), bounce_stoploss: cells[13].textContent.trim()
                };
            });
            const notesTextarea = document.getElementById(notesTextareaId);
            if (notesTextarea) { dataToSave.global_notes = notesTextarea.value; }
            statusElement.textContent = 'Saving...';
            dbRef.set(dataToSave).then(() => {
                statusElement.textContent = 'Saved.'; setTimeout(() => { statusElement.textContent = '' }, 2000);
            }).catch(e => { statusElement.textContent = `Error: ${e.message}`; console.error("Error saving setups table:", e); });
        }

        const saveJournalEntry = () => {
            clearTimeout(STATE.journalSaveTimer);
            STATE.journalSaveTimer = setTimeout(() => {
                if (!STATE.isMasterUser) return;
                const safeSymbol = getSafeSymbol(DOM.journalSymbolEl.value);
                const yyyymmdd = getYYYYMMDD(STATE.selectedDate);
                const timeframe = DOM.journalTimeframeEl.value;
                const text = DOM.journalEntryEl.value;
                DOM.saveStatus.textContent = 'Saving...';
                if (!STATE.journalText[safeSymbol]) STATE.journalText[safeSymbol] = {};
                if (!STATE.journalText[safeSymbol][yyyymmdd]) STATE.journalText[safeSymbol][yyyymmdd] = {};
                STATE.journalText[safeSymbol][yyyymmdd][timeframe] = text;
                dbRefs.journalText.child(safeSymbol).child(yyyymmdd).child(timeframe).set(text)
                    .then(() => { DOM.saveStatus.textContent = 'Saved.'; renderDateNavigation(); setTimeout(() => DOM.saveStatus.textContent = '', 2000); })
                    .catch(e => DOM.saveStatus.textContent = `Error: ${e.message}`);
            }, 750);
        };

        const savePersistentNotes = () => {
            clearTimeout(STATE.notesSaveTimer);
            STATE.notesSaveTimer = setTimeout(() => {
                if (!STATE.isMasterUser) return;
                dbRefs.persistentNotes.set(DOM.persistentNotesEl.value).catch(e => console.error("Error saving persistent notes:", e));
            }, 750);
        };

        const saveTrackerScratchpad = () => {
            clearTimeout(STATE.trackerSaveTimer);
            STATE.trackerSaveTimer = setTimeout(() => {
                if (!STATE.isMasterUser) return;
                dbRefs.trackerScratchpad.set(DOM.trackerScratchpadEl.value).catch(e => console.error("Error saving tracker scratchpad:", e));
            }, 750);
        };
        
        const savePrimarySetupsNotes = () => {
            if (!STATE.isMasterUser) return;
            saveSetupsTable(DOM.setupsTable1, dbRefs.setups1, DOM.setupsSaveStatus1, 'primary-setups-notes');
        };
        
        const saveSecondarySetupsNotes = () => {
            if (!STATE.isMasterUser) return;
            saveSetupsTable(DOM.setupsTable2, dbRefs.setups2, DOM.setupsSaveStatus2, 'secondary-setups-notes');
        };

        function handleFileUpload(files) {
            if (!STATE.isMasterUser || !files || files.length === 0) return;
            DOM.uploadProgress.style.display = 'block';
            const safeSymbol = getSafeSymbol(DOM.journalSymbolEl.value);
            const timeframe = DOM.journalTimeframeEl.value;
            Array.from(files).forEach((file, index) => {
                if (!file.type.startsWith('image/')) return;
                const fileName = `${Date.now()}_${file.name}`;
                const storagePath = `journal_images/${safeSymbol}/${timeframe}/${fileName}`;
                const uploadTask = storage.ref(storagePath).put(file);
                uploadTask.on('state_changed', 
                    (s) => { DOM.uploadProgress.textContent = `Uploading ${index + 1}/${files.length}: ${Math.round((s.bytesTransferred / s.totalBytes) * 100)}%`; },
                    (e) => { console.error("Upload Failed:", e); DOM.uploadProgress.textContent = `Upload Failed: ${e.code}`; },
                    () => {
                        uploadTask.snapshot.ref.getDownloadURL().then((url) => {
                            const imageData = { url, fileName, timestamp: firebase.database.ServerValue.TIMESTAMP };
                            dbRefs.journalImages.child(safeSymbol).child(timeframe).push(imageData);
                            if (index === files.length - 1) { DOM.uploadProgress.textContent = 'Upload Complete!'; setTimeout(() => { DOM.uploadProgress.textContent = ''; }, 2000); }
                        });
                    }
                );
            });
        }

        function handleGenericLibraryUpload(files, libraryType, progressElement, dbRef) {
            if (!STATE.isMasterUser || !files || files.length === 0) return;
            progressElement.style.display = 'block';
            Array.from(files).forEach((file, index) => {
                if (!file.type.startsWith('image/')) return;
                const fileName = `${Date.now()}_${file.name}`;
                const storagePath = `${libraryType}/${fileName}`;
                const uploadTask = storage.ref(storagePath).put(file);
                uploadTask.on('state_changed', 
                    (s) => { progressElement.textContent = `Uploading ${index + 1}/${files.length}: ${Math.round((s.bytesTransferred / s.totalBytes) * 100)}%`; },
                    (e) => { console.error(`${libraryType} Upload Failed:`, e); progressElement.textContent = `Upload Failed: ${e.code}`; },
                    () => {
                        uploadTask.snapshot.ref.getDownloadURL().then((url) => {
                            const imageData = { url, fileName, timestamp: firebase.database.ServerValue.TIMESTAMP, caption: '' };
                            dbRef.push(imageData);
                            if (index === files.length - 1) { progressElement.textContent = 'Upload Complete!'; setTimeout(() => { progressElement.textContent = ''; }, 2000); }
                        });
                    }
                );
            });
        }

        function handleChartLibrary2Upload(files, folderName) {
            if (!STATE.isMasterUser || !files || files.length === 0) return;
            const folderCard = document.querySelector(`.cl2-folder-card[data-folder="${folderName}"]`);
            if(folderCard) folderCard.style.outline = '2px solid var(--link-color)';
            Array.from(files).forEach((file, index) => {
                if (!file.type.startsWith('image/')) return;
                const fileName = `${Date.now()}_${file.name}`;
                const storagePath = `chart_library_2/${folderName}/${fileName}`;
                const uploadTask = storage.ref(storagePath).put(file);
                uploadTask.on('state_changed', null, 
                    (e) => { console.error(`Upload to ${folderName} Failed:`, e); alert(`Upload failed for ${file.name}.`); if(folderCard) folderCard.style.outline = 'none'; },
                    () => {
                        uploadTask.snapshot.ref.getDownloadURL().then((url) => {
                            const imageData = { url, fileName, timestamp: firebase.database.ServerValue.TIMESTAMP };
                            dbRefs.chartLibrary2.child(folderName).push(imageData);
                            if (index === files.length - 1 && folderCard) folderCard.style.outline = 'none';
                        });
                    }
                );
            });
        }

        function calculateNetResult(trade, exitPrice) {
            const entry = parseFloat(trade.entry), posValue = parseFloat(trade.size), exit = parseFloat(exitPrice);
            if (isNaN(entry) || isNaN(posValue) || isNaN(exit)) return { net_result: 0, entry_fee: 0, exit_fee: 0 };
            const entryFee = posValue * CONFIG.TRADE_SETTINGS.FEE_RATE;
            const exitPosValue = (exit / entry) * posValue;
            const exitFee = exitPosValue * CONFIG.TRADE_SETTINGS.FEE_RATE;
            const positionQty = posValue / entry;
            const grossResult = trade.type === "Long" ? (exit - entry) * positionQty : (entry - exit) * positionQty;
            return { net_result: grossResult - entryFee - exitFee, entry_fee: entryFee, exit_fee: exitFee };
        }

        function completeTrade(tradeId, outcome) {
            dbRefs.trades.child(tradeId).once('value', snapshot => {
                const trade = snapshot.val(); if (!trade) return;
                const exitPriceStr = prompt(`Enter exact exit price:`, outcome === 'win' ? trade.target : trade.stoploss);
                if (exitPriceStr === null) return;
                const exitPrice = parseFloat(exitPriceStr);
                if (isNaN(exitPrice)) return alert("Invalid exit price.");
                const result = calculateNetResult(trade, exitPrice);
                const completedTrade = { ...trade, ...result, closed_date: firebase.database.ServerValue.TIMESTAMP, exit_price: exitPrice, };
                dbRefs.completedTrades.push(completedTrade).then(() => dbRefs.trades.child(tradeId).remove());
            });
        }

        // --- MODAL LOGIC ---
        function openImageModal(imageArray, clickedIndex) {
            STATE.modalImageGallery = imageArray;
            STATE.modalImageIndex = clickedIndex;
            displayModalImage();
            DOM.imageModal.style.display = 'flex';
        }

        function displayModalImage() {
            if (STATE.modalImageIndex < 0 || STATE.modalImageIndex >= STATE.modalImageGallery.length) return;
            const currentImage = STATE.modalImageGallery[STATE.modalImageIndex];
            DOM.modalImageContent.src = currentImage.url;
            DOM.modalCaption.textContent = currentImage.caption || '';
            DOM.modalPrevBtn.style.display = STATE.modalImageIndex > 0 ? 'flex' : 'none';
            DOM.modalNextBtn.style.display = STATE.modalImageIndex < STATE.modalImageGallery.length - 1 ? 'flex' : 'none';
        }

        function closeModal() {
            DOM.imageModal.style.display = 'none';
            STATE.modalImageGallery = [];
            STATE.modalImageIndex = -1;
        }

        let noteModalSaveTimer = null;
        function openNoteForEditing(noteId) {
            const note = STATE.generalNotes[noteId];
            if (!note) return;

            DOM.noteModalTitle.value = note.title || '';
            DOM.noteModalContent.value = note.content || '';
            DOM.noteEditModal.dataset.currentNoteId = noteId;
            DOM.noteEditModal.style.display = 'flex';
            
            setTimeout(() => { 
                autoResizeTextarea(DOM.noteModalContent);
                DOM.noteModalContent.focus();
            }, 0);

            DOM.noteModalTitle.readOnly = !STATE.isMasterUser;
            DOM.noteModalContent.readOnly = !STATE.isMasterUser;
        }

        function saveNoteFromModal() {
            if (!STATE.isMasterUser) return;
            const noteId = DOM.noteEditModal.dataset.currentNoteId;
            if (!noteId) return;

            clearTimeout(noteModalSaveTimer);
            noteModalSaveTimer = setTimeout(() => {
                const newTitle = DOM.noteModalTitle.value.trim();
                const newContent = DOM.noteModalContent.value;
                dbRefs.generalNotes.child(noteId).update({
                    title: newTitle,
                    content: newContent
                });
            }, 500);
        }

        function closeNoteModal() {
            saveNoteFromModal(); 
            clearTimeout(noteModalSaveTimer);
            
            DOM.noteEditModal.style.display = 'none';
            DOM.noteEditModal.dataset.currentNoteId = '';
            DOM.noteModalTitle.value = '';
            DOM.noteModalContent.value = '';

            renderNotes(STATE.generalNotes);
        }

        // --- EVENT LISTENERS ---
         function setupEventListeners() {
            document.getElementById('key-opens-container').addEventListener('input', e => {
                if(e.target.matches('.key-open-note')) {
                    autoResizeTextarea(e.target);
                    saveLevelNotes(e.target);
                }
            });
            DOM.themeToggle.addEventListener('change', (e) => {
                const theme = e.target.checked ? 'dark' : 'light';
                document.documentElement.setAttribute('data-theme', theme);
                localStorage.setItem('theme', theme);
            });

            DOM.tabs.addEventListener('click', (e) => {
                if (!e.target.matches('.tab-link')) return;
                
                document.querySelectorAll('.tab-link, .tab-content').forEach(el => el.classList.remove('active'));
                
                e.target.classList.add('active');
                const tabId = e.target.dataset.tab;
                const newTabContent = document.getElementById(`${tabId}-tab`);
                
                if (newTabContent) {
                    newTabContent.classList.add('active');

                    if (!newTabContent.dataset.sectionsInitialized) {
                        openDefaultSectionsInContainer(newTabContent);
                        newTabContent.dataset.sectionsInitialized = 'true';
                    }
                }
                
                DOM.statsPanelContainer.style.display = (tabId === 'tracker' || tabId === 'journal') ? 'block' : 'none';
                if (tabId === 'journal') updateJournalView();
                if (tabId === 'sr-levels') renderSrLevels();
            });

            DOM.statsFab.addEventListener('click', () => DOM.statsPanel.classList.toggle('active'));
            DOM.closeStatsBtn.addEventListener('click', () => DOM.statsPanel.classList.remove('active'));
            document.addEventListener('click', (e) => {
                if (!DOM.statsPanel.contains(e.target) && !DOM.statsFab.contains(e.target) && DOM.statsPanel.classList.contains('active')) {
                    DOM.statsPanel.classList.remove('active');
                }
            });

            DOM.addTradeForm.addEventListener('submit', handleAddTradeSubmit);
            
            document.body.addEventListener('click', (e) => {
                const header = e.target.closest('.collapsible-header');
                if (header) {
                    const section = header.parentElement;
                    const content = section.querySelector('.collapsible-content');
                    const toggleBtn = section.querySelector('.collapsible-toggle-btn');
                    section.classList.toggle('is-open');
                    toggleBtn.textContent = section.classList.contains('is-open') ? '−' : '+';
                    toggleBtn.style.transform = section.classList.contains('is-open') ? 'rotate(180deg)' : 'rotate(0deg)';
                    if (section.classList.contains('is-open')) {
                        content.style.maxHeight = content.scrollHeight + 'px';
                        setTimeout(() => { if (section.classList.contains('is-open')) content.style.maxHeight = content.scrollHeight + 'px'; }, 150);
                    } else { content.style.maxHeight = '0px'; }
                }

                if (handleAttachmentActions(e)) return;

                if (e.target.matches('.ema-pill-btn')) {
                    e.stopPropagation();
                    const pillBtn = e.target;
                    const group = pillBtn.closest('.pill-button-group');
                    group.querySelectorAll('.ema-pill-btn').forEach(btn => btn.classList.remove('active'));
                    pillBtn.classList.add('active');
                    renderEmaSnapshot(pillBtn.dataset.symbol);
                } else if (e.target.closest('.sentiment-buttons button')) {
                    handleSentimentLog(e);
                } else if (e.target.closest('#setups-image-container, #image-library-container, #chart-library-2-container, #chart-library-2-preview-container')) {
                    handleGenericImageLibraryClick(e);
                } else if (e.target.closest('#trades-tbody, #completed-trades-tbody')) {
                    handleTradeAction(e);
                } else if (e.target.closest('#sentiment-receipts-tbody')) {
                    handleSentimentAction(e);
                } else if (e.target.id === 'toggle-all-sentiments') {
                    STATE.sentimentShowAll = true;
                    STATE.sentimentCurrentPage = 1;
                    renderSentimentReceipts();
                } else if (e.target.id === 'sentiment-prev-page') {
                    if (STATE.sentimentCurrentPage > 1) {
                        STATE.sentimentCurrentPage--;
                        renderSentimentReceipts();
                    }
                } else if (e.target.id === 'sentiment-next-page') {
                    const totalPages = Math.ceil(Object.keys(STATE.allSentimentReceipts).length / STATE.sentimentItemsPerPage);
                    if (STATE.sentimentCurrentPage < totalPages) {
                        STATE.sentimentCurrentPage++;
                        renderSentimentReceipts();
                    }
                } else if (e.target.id === 'toggle-old-trades') {
                    toggleHistoricalRows('completed-trades-tbody', e.target);
                } else if (e.target.id === 'toggle-old-setups-images') {
                    toggleHistoricalImages('setups-image-container', e.target);
                }
            });

            if (DOM.createNewNoteBtn) {
                DOM.createNewNoteBtn.addEventListener('click', () => {
                    if (!STATE.isMasterUser) return;
                    const title = prompt("Enter a title for the new note:");
                    if (title && title.trim()) {
                        dbRefs.generalNotes.push({
                            title: title.trim(),
                            content: '',
                            timestamp: firebase.database.ServerValue.TIMESTAMP
                        });
                    }
                });
            }

            if (DOM.notesContainer) {
                DOM.notesContainer.addEventListener('click', (e) => {
                    const header = e.target.closest('.note-item-header');
                    const deleteBtn = e.target.closest('.note-delete-btn');

                    if (deleteBtn && STATE.isMasterUser) {
                        e.stopPropagation();
                        const noteId = deleteBtn.dataset.noteId;
                        if (confirm(`Are you sure you want to delete this note?`)) {
                            dbRefs.generalNotes.child(noteId).remove();
                        }
                        return;
                    }

                    if (header) {
                        const noteId = header.dataset.noteId;
                        openNoteForEditing(noteId);
                    }
                });
            }

            DOM.noteModalClose.addEventListener('click', closeNoteModal);
            DOM.noteEditModal.addEventListener('click', e => {
                if (e.target.id === 'note-edit-modal') closeNoteModal();
            });
            DOM.noteModalTitle.addEventListener('input', saveNoteFromModal);
            DOM.noteModalContent.addEventListener('input', (e) => {
                autoResizeTextarea(e.target);
                saveNoteFromModal();
            });

            document.body.addEventListener('blur', (e) => {
                if (e.target.matches('.setups-table .editable-setup-cell')) {
                    const table = e.target.closest('.setups-table');
                    const row = e.target.closest('tr');
                    
                    applyHighlightingToSetupsTable(table);
                    if (row) {
                        calculateAndDisplayPercentages(row);
                    }

                    if (table.id === 'primary-setups-table') {
                        saveSetupsTable(DOM.setupsTable1, dbRefs.setups1, DOM.setupsSaveStatus1, 'primary-setups-notes');
                    } else {
                        saveSetupsTable(DOM.setupsTable2, dbRefs.setups2, DOM.setupsSaveStatus2, 'secondary-setups-notes');
                    }
                }
            }, true);

            DOM.trackerScratchpadEl.addEventListener('input', (e) => { 
                autoResizeTextarea(e.target); 
                debouncedResizeParent(e.target);
                saveTrackerScratchpad(); 
            });
            
            DOM.primarySetupsNotes.addEventListener('input', (e) => {
                autoResizeTextarea(e.target);
                debouncedResizeParent(e.target);
                clearTimeout(STATE.setups1NotesTimer);
                STATE.setups1NotesTimer = setTimeout(savePrimarySetupsNotes, 750);
            });
            DOM.secondarySetupsNotes.addEventListener('input', (e) => {
                autoResizeTextarea(e.target);
                debouncedResizeParent(e.target);
                clearTimeout(STATE.setups2NotesTimer);
                STATE.setups2NotesTimer = setTimeout(saveSecondarySetupsNotes, 750);
            });

            DOM.libraryImageUpload.addEventListener('change', (e) => handleGenericLibraryUpload(e.target.files, 'image_library', DOM.libraryUploadProgress, dbRefs.imageLibrary));
            DOM.setupsImageUpload.addEventListener('change', (e) => handleGenericLibraryUpload(e.target.files, 'setups_images', DOM.setupsUploadProgress, dbRefs.setupsImages));
            DOM.tradeImageUploader.addEventListener('change', (e) => handleAttachmentImageUpload(e.target.files));

            DOM.modalClose.addEventListener('click', closeModal);
            DOM.imageModal.addEventListener('click', (e) => { if (e.target.id === 'image-modal') closeModal(); });
            DOM.modalPrevBtn.addEventListener('click', () => { if (STATE.modalImageIndex > 0) { STATE.modalImageIndex--; displayModalImage(); } });
            DOM.modalNextBtn.addEventListener('click', () => { if (STATE.modalImageIndex < STATE.modalImageGallery.length - 1) { STATE.modalImageIndex++; displayModalImage(); } });

            DOM.tradesTbody.addEventListener('blur', (e) => { if (e.target.matches('.editable-cell')) handleLiveTradeUpdate(e.target); }, true);

            [DOM.journalSymbolEl, DOM.journalTimeframeEl, DOM.journalImageFilterEl].forEach(el => el.addEventListener('change', updateJournalView));
            DOM.dateButtonsContainer.addEventListener('click', (e) => {
                if (e.target.matches('.date-nav-btn')) {
                    const parts = e.target.dataset.date.split('-');
                    STATE.selectedDate = new Date(Date.UTC(parts[0], parseInt(parts[1], 10) - 1, parts[2]));
                    STATE.centerDate = new Date(STATE.selectedDate);
                    updateJournalView();
                }
            });
            DOM.datePrevBtn.addEventListener('click', () => { STATE.centerDate.setUTCDate(STATE.centerDate.getUTCDate() - 5); renderDateNavigation(); });
            DOM.dateNextBtn.addEventListener('click', () => { STATE.centerDate.setUTCDate(STATE.centerDate.getUTCDate() + 5); renderDateNavigation(); });

            DOM.journalEntryEl.addEventListener('input', (e) => { 
                autoResizeTextarea(e.target); 
                debouncedResizeParent(e.target);
                saveJournalEntry(); 
            });
            DOM.persistentNotesEl.addEventListener('input', (e) => { 
                autoResizeTextarea(e.target); 
                debouncedResizeParent(e.target);
                savePersistentNotes(); 
            });
            DOM.favouriteBtn.addEventListener('click', handleFavouriteClick);
            DOM.journalImageUpload.addEventListener('change', (e) => handleFileUpload(e.target.files));

            DOM.journalTab.addEventListener('click', (e) => {
                if (e.target.closest('.delete-journal-image')) { handleImageDelete(e); return; }
                const img = e.target.closest('#journal-images-container img');
                if(img) {
                    const allImageElements = DOM.journalImagesContainer.querySelectorAll('img');
                    const imageArray = Array.from(allImageElements).map(el => ({ url: el.dataset.fullSrc, caption: el.dataset.caption }));
                    const clickedIndex = Array.from(allImageElements).indexOf(img);
                    openImageModal(imageArray, clickedIndex);
                }
            });

            ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => { DOM.journalTab.addEventListener(eventName, e => { e.preventDefault(); e.stopPropagation(); }); });
            ['dragenter', 'dragover'].forEach(eventName => { DOM.journalTab.addEventListener(eventName, () => { if (STATE.isMasterUser) DOM.journalTab.classList.add('drag-over'); }); });
            DOM.journalTab.addEventListener('dragleave', () => DOM.journalTab.classList.remove('drag-over'));
            DOM.journalTab.addEventListener('drop', (e) => {
                DOM.journalTab.classList.remove('drag-over');
                if (STATE.isMasterUser && e.dataTransfer?.files.length > 0) handleFileUpload(e.dataTransfer.files);
            });

            [DOM.srSymbolEl, DOM.srLookbackEl].forEach(el => el.addEventListener('change', renderSrLevels));

            DOM.srLegendHeader.addEventListener('click', () => {
                const isCollapsed = DOM.srLegendContent.style.display === 'none';
                DOM.srLegendContent.style.display = isCollapsed ? 'block' : 'none';
                DOM.srLegendHeader.classList.toggle('collapsed', !isCollapsed);
                DOM.srLegendToggleBtn.textContent = isCollapsed ? '−' : '+';
                DOM.srLegendToggleBtn.style.transform = isCollapsed ? 'rotate(0deg)' : 'rotate(180deg)';
            });
        }

    // --- EVENT HANDLER LOGIC ---
    function calculateTradeMetrics(tradeData) {
        const entry = parseFloat(tradeData.entry);
        const stoploss = parseFloat(tradeData.stoploss);
        const target = parseFloat(tradeData.target);
        const size = parseFloat(tradeData.size);
        const type = tradeData.type;

        if ([entry, stoploss, target, size].some(v => isNaN(v) || v <= 0)) {
            return { rr: 0, estimated_total_fee: 0, expected_profit: 0, expected_loss: 0, expected_profit_percent: 0, expected_loss_percent: 0 };
        }

        const { FEE_RATE } = CONFIG.TRADE_SETTINGS;
        const positionQty = size / entry;
        const entryFee = size * FEE_RATE;

        let potentialProfit, potentialLoss;
        if (type === 'Long') {
            potentialProfit = positionQty * (target - entry);
            potentialLoss = positionQty * (entry - stoploss);
        } else { // Short
            potentialProfit = positionQty * (entry - target);
            potentialLoss = positionQty * (stoploss - entry);
        }

        const rr = (potentialLoss > 0) ? (potentialProfit / potentialLoss) : 0;

        const exitValueAtTarget = (target / entry) * size;
        const exitFeeAtTarget = exitValueAtTarget * FEE_RATE;
        const estimated_total_fee = entryFee + exitFeeAtTarget;
        const expected_profit = potentialProfit - estimated_total_fee;

        const exitValueAtStop = (stoploss / entry) * size;
        const exitFeeAtStop = exitValueAtStop * FEE_RATE;
        const expected_loss = potentialLoss + entryFee + exitFeeAtStop;
        
        const expected_profit_percent = (expected_profit / size) * 100;
        const expected_loss_percent = (expected_loss / size) * 100;

        return {
            rr: rr.toFixed(2),
            estimated_total_fee: estimated_total_fee,
            expected_profit: expected_profit,
            expected_loss: expected_loss,
            expected_profit_percent: expected_profit_percent,
            expected_loss_percent: expected_loss_percent
        };
    }

    function handleAddTradeSubmit(e) {
        e.preventDefault(); if (!STATE.isMasterUser) return;
        const trade = {
            symbol: document.getElementById('trade-symbol').value, type: document.getElementById('trade-type').value,
            entry: parseFloat(document.getElementById('entry-price').value), stoploss: parseFloat(document.getElementById('stop-loss').value),
            target: parseFloat(document.getElementById('target').value), size: parseFloat(document.getElementById('position-value').value),
            date: firebase.database.ServerValue.TIMESTAMP, entry_prices: []
        };
        if (Object.values(trade).some(val => val === null || (isNaN(val) && typeof val === 'number'))) return alert('Please fill all fields correctly.');
        
        trade.entry_prices.push(trade.entry);
        const metrics = calculateTradeMetrics(trade);
        const tradeWithMetrics = { ...trade, ...metrics };
        
        dbRefs.trades.push(tradeWithMetrics).then(() => e.target.reset()).catch(error => alert(`Error adding trade: ${error.message}`));
    }
    
    function handleLiveTradeUpdate(cell) {
        if (!STATE.isMasterUser) return;
        const tradeId = cell.dataset.id;
        const fieldToUpdate = cell.dataset.field;
        const tradeRef = dbRefs.trades.child(tradeId);

        tradeRef.once('value', snapshot => {
            const trade = snapshot.val();
            if (!trade) {
                alert('Error: Trade not found.');
                return;
            }
            
            const updates = {};
            
            if (fieldToUpdate === 'entry_prices') {
                const newPricesArray = cell.textContent.split(',').map(s => parseFloat(s.trim())).filter(n => !isNaN(n) && n > 0);
                if (newPricesArray.length === 0) {
                    alert("Invalid entry prices list.");
                    cell.textContent = (trade.entry_prices || [trade.entry]).join(', '); // Restore from snapshot
                    return;
                }
                updates.entry_prices = newPricesArray;
                updates.note = (trade.note || '') + `\nEntry list updated ${new Date().toLocaleString()}`;
                tradeRef.update(updates);
                return; 
            } 

            let newValue = parseFloat(cell.textContent.replace(/[^0-9.-]/g, ''));
            const precision = ['entry', 'stoploss', 'target'].includes(fieldToUpdate) ? 4 : 2;

            if (isNaN(newValue)) {
                alert('Invalid number.');
                cell.textContent = parseFloat(trade[fieldToUpdate]).toFixed(precision); // Restore from snapshot
                return;
            }

            if (parseFloat(trade[fieldToUpdate]).toFixed(precision) === newValue.toFixed(precision)) {
                cell.textContent = newValue.toFixed(precision); // Just format it correctly, no DB update needed
                return;
            }
            
            updates[fieldToUpdate] = newValue;
            
            const tempTradeForCalc = { ...trade, ...updates };
            const newMetrics = calculateTradeMetrics(tempTradeForCalc);
            
            Object.assign(updates, newMetrics);
            
            updates.note = (trade.note || '') + `\n${fieldToUpdate} updated to ${newValue.toFixed(precision)} on ${new Date().toLocaleString()}`;
            
            tradeRef.update(updates).catch(error => {
                alert('Failed to update trade: ' + error.message);
                cell.textContent = parseFloat(trade[fieldToUpdate]).toFixed(precision);
            });
        });
    }

    function handleSentimentLog(e) {
        const button = e.target.closest('.sentiment-buttons button'); if (!button) return;
        const { asset, sentiment } = button.dataset; if (!asset || !sentiment) return;
        dbRefs.sentimentReceipts.push({ asset, sentiment, timestamp: firebase.database.ServerValue.TIMESTAMP, viewerId: getViewerId() });
    }

    function handleSentimentAction(e) {
        if (!STATE.isMasterUser) return;
        const editBtn = e.target.closest('.edit-sentiment-note-btn'); if (editBtn) handleSentimentNoteEdit(editBtn);
        const deleteBtn = e.target.closest('.delete-sentiment-btn'); if (deleteBtn) handleSentimentDelete(deleteBtn);
    }

    function handleSentimentDelete(button) {
        const receiptId = button.dataset.id; if (!receiptId) return;
        if (confirm('Delete this log entry?')) dbRefs.sentimentReceipts.child(receiptId).remove();
    }

    function handleSentimentNoteEdit(button) {
        const receiptId = button.dataset.id; if (!receiptId) return;
        const receiptRef = dbRefs.sentimentReceipts.child(receiptId);
        receiptRef.child('note').once('value', snapshot => {
            const newNote = prompt('Enter note:', snapshot.val() || "");
            if (newNote !== null) receiptRef.update({ note: newNote });
        });
    }

    function handleAddStaggeredEntry(tradeId) {
        if (!STATE.isMasterUser) return;
        const tradeRef = dbRefs.trades.child(tradeId);
        tradeRef.once('value', snapshot => {
            const currentTrade = snapshot.val(); if (!currentTrade) return alert('Error: Trade not found.');
            const newEntryPriceStr = prompt("Enter NEW entry price:"); if (newEntryPriceStr === null) return;
            const newPositionValueStr = prompt("Enter value ($) of this NEW position:"); if (newPositionValueStr === null) return;
            const newEntryPrice = parseFloat(newEntryPriceStr), newPositionValue = parseFloat(newPositionValueStr);
            if (isNaN(newEntryPrice) || isNaN(newPositionValue) || newEntryPrice <= 0 || newPositionValue <= 0) return alert("Invalid input.");
            
            const currentSize = parseFloat(currentTrade.size), currentEntry = parseFloat(currentTrade.entry);
            const totalValue = currentSize + newPositionValue, totalQuantity = (currentSize / currentEntry) + (newPositionValue / newEntryPrice);
            const newAverageEntryPrice = totalValue / totalQuantity;
            const updatedEntryPrices = currentTrade.entry_prices || [currentTrade.entry]; updatedEntryPrices.push(newEntryPrice);
            
            const tempTradeForCalc = {
                ...currentTrade,
                entry: newAverageEntryPrice,
                size: totalValue
            };
            const newMetrics = calculateTradeMetrics(tempTradeForCalc);

            const updatedTrade = {
                ...currentTrade,
                entry: newAverageEntryPrice,
                size: totalValue,
                entry_prices: updatedEntryPrices,
                ...newMetrics,
                note: (currentTrade.note || '') + `\n+ Added $${newPositionValue.toFixed(2)} @ $${newEntryPrice.toFixed(4)} on ${new Date().toLocaleString()}`
            };
            tradeRef.update(updatedTrade);
        });
    }

    function handleGenericImageLibraryClick(e) {
        const clickedImg = e.target.closest('img');
        if (clickedImg?.dataset.fullSrc) {
            const galleryContainer = clickedImg.closest('#image-library-container, #setups-image-container, .cl2-image-grid, #chart-library-2-preview-container, .trade-image-thumbnails');
            if (galleryContainer) {
                const allImageElements = galleryContainer.querySelectorAll('img');
                const imageArray = Array.from(allImageElements).map(el => ({ url: el.dataset.fullSrc, caption: el.dataset.caption }));
                const clickedIndex = Array.from(allImageElements).indexOf(clickedImg);
                if (clickedIndex > -1) openImageModal(imageArray, clickedIndex);
            }
            return;
        }
        if (e.target.closest('#image-library-container')) handleLibraryActions(e, 'image_library', dbRefs.imageLibrary);
        else if (e.target.closest('#setups-image-container')) handleLibraryActions(e, 'setups_images', dbRefs.setupsImages);
        else if (e.target.closest('#chart-library-2-container')) handleChartLibrary2Click(e);
    }

    function handleLibraryActions(e, libraryType, dbRef) {
        const deleteBtn = e.target.closest('.delete-library-image'), editBtn = e.target.closest('.edit-caption-btn');
        if (deleteBtn && STATE.isMasterUser) {
            const { id, filename } = deleteBtn.dataset;
            if (confirm(`Delete this image?\n\n${filename}`)) {
                const storagePath = `${libraryType}/${filename}`;
                storage.ref(storagePath).delete().then(() => dbRef.child(id).remove()).catch((err) => {
                    if (err.code === 'storage/object-not-found') dbRef.child(id).remove(); else alert('Error deleting image.');
                });
            }
        } else if (editBtn && STATE.isMasterUser) {
            const { id } = editBtn.dataset;
            const imageRef = dbRef.child(id);
            imageRef.child('caption').once('value', snapshot => {
                const newCaption = prompt('Enter image caption:', snapshot.val() || "");
                if (newCaption !== null) imageRef.update({ caption: newCaption.trim() });
            });
        }
    }

    function handleChartLibrary2Click(e) {
        const folderCard = e.target.closest('.cl2-folder-card'), backBtn = e.target.closest('.cl2-back-button'), deleteBtn = e.target.closest('.delete-library-image');
        if (folderCard) { STATE.currentCl2Folder = folderCard.dataset.folder; renderFolderContents(STATE.currentCl2Folder); return; }
        if (backBtn) { STATE.currentCl2Folder = null; renderChartLibrary2Folders(); return; }
        if (deleteBtn && STATE.isMasterUser) {
            const { folder, id, filename } = deleteBtn.dataset;
            if (confirm(`Delete this image from ${folder}?\n\n${filename}`)) {
                const storagePath = `chart_library_2/${folder}/${filename}`;
                storage.ref(storagePath).delete().then(() => dbRefs.chartLibrary2.child(folder).child(id).remove()).catch((err) => {
                    if (err.code === 'storage/object-not-found') dbRefs.chartLibrary2.child(folder).child(id).remove(); else alert('Error deleting image.');
                });
            }
        }
    }

    function handleTradeAction(e) {
        if (!STATE.isMasterUser) return;
        if (STATE.isMerging) {
            const targetRow = e.target.closest('tr');
            if (targetRow && targetRow.parentElement.id === 'completed-trades-tbody' && !e.target.closest('button')) {
                const absorbedTradeId = targetRow.querySelector('.action-buttons button')?.dataset.id;
                if (absorbedTradeId) executeMerge(STATE.mergeBaseTradeId, absorbedTradeId);
            }
            return;
        }
        const button = e.target.closest('button'); if (!button) return;
        const { id } = button.dataset;
        const isCompleted = button.closest('tbody').id === 'completed-trades-tbody';
        const tradeRef = isCompleted ? dbRefs.completedTrades.child(id) : dbRefs.trades.child(id);
        if (button.matches('.win-btn')) completeTrade(id, 'win');
        else if (button.matches('.loss-btn')) completeTrade(id, 'loss');
        else if (button.matches('.add-to-position-btn')) handleAddStaggeredEntry(id);
        else if (button.matches('.merge-btn-completed')) initiateMerge(id);
        else if (button.matches('.delete-btn, .delete-btn-completed')) { if (confirm('Delete this trade?')) { resetMergeState(); tradeRef.remove(); } } 
        else if (button.matches('.note-btn, .note-btn-completed')) {
            tradeRef.child('note').once('value', snapshot => { const newNote = prompt("Enter note:", snapshot.val() || ""); if (newNote !== null) tradeRef.update({ note: newNote }); });
        }
    }
    
    function handleAttachmentActions(e) {
        const attachBtn = e.target.closest('.attach-image-btn'); if (attachBtn) { handleAttachAttachmentClick(attachBtn.dataset.id, attachBtn.dataset.type); return true; }
        const delImgBtn = e.target.closest('.delete-trade-image'); if (delImgBtn) { const { entryId, entryType, imageId, filename } = delImgBtn.dataset; handleDeleteAttachmentImage(entryId, entryType, imageId, filename); return true; }
        const img = e.target.closest('.trade-image-thumbnails img'); if (img) { handleGenericImageLibraryClick(e); return true; }
        return false;
    }

    function handleAttachAttachmentClick(entryId, entryType) {
        if (!STATE.isMasterUser) return;
        STATE.imageUploadContext = { id: entryId, type: entryType };
        DOM.tradeImageUploader.value = null; DOM.tradeImageUploader.click();
    }

    function handleAttachmentImageUpload(files) {
        if (!STATE.isMasterUser || !files || files.length === 0) return;
        const { id, type } = STATE.imageUploadContext; if (!id || !type) return;
        let dbRefPath, storagePathPrefix;
        switch (type) {
            case 'live': dbRefPath = CONFIG.DB_PATHS.TRADES; storagePathPrefix = `trade_attachments/${id}/`; break;
            case 'completed': dbRefPath = CONFIG.DB_PATHS.COMPLETED_TRADES; storagePathPrefix = `trade_attachments/${id}/`; break;
            case 'sentiment': dbRefPath = CONFIG.DB_PATHS.SENTIMENT_RECEIPTS; storagePathPrefix = `sentiment_attachments/${id}/`; break;
            default: return;
        }
        const entryDbRef = database.ref(dbRefPath).child(id);
        Array.from(files).forEach((file) => {
            if (!file.type.startsWith('image/')) return;
            const fileName = `${Date.now()}_${file.name}`;
            const storagePath = `${storagePathPrefix}${fileName}`;
            const uploadTask = storage.ref(storagePath).put(file);
            uploadTask.on('state_changed', null, (e) => { alert(`Upload failed for ${file.name}.`); }, () => {
                uploadTask.snapshot.ref.getDownloadURL().then((url) => {
                    entryDbRef.child('attachedImages').push({ url, fileName, timestamp: firebase.database.ServerValue.TIMESTAMP });
                });
            });
        });
    }

    function handleDeleteAttachmentImage(entryId, entryType, imageId, fileName) {
        if (!STATE.isMasterUser || !entryId || !entryType || !imageId || !fileName) return;
        if (confirm(`Delete this attachment?\n\n${fileName}`)) {
            let dbRefPath, storagePathPrefix;
            switch (entryType) {
                case 'live': dbRefPath = CONFIG.DB_PATHS.TRADES; storagePathPrefix = `trade_attachments/${entryId}/`; break;
                case 'completed': dbRefPath = CONFIG.DB_PATHS.COMPLETED_TRADES; storagePathPrefix = `trade_attachments/${entryId}/`; break;
                case 'sentiment': dbRefPath = CONFIG.DB_PATHS.SENTIMENT_RECEIPTS; storagePathPrefix = `sentiment_attachments/${entryId}/`; break;
                default: return;
            }
            const storagePath = `${storagePathPrefix}${fileName}`;
            const imageDbRef = database.ref(dbRefPath).child(entryId).child('attachedImages').child(imageId);
            storage.ref(storagePath).delete().then(() => imageDbRef.remove()).catch((err) => {
                if (err.code === 'storage/object-not-found') imageDbRef.remove(); else alert('Error deleting attachment.');
            });
        }
    }

    function handleImageDelete(e) {
        const button = e.target.closest('.delete-journal-image'); if (!STATE.isMasterUser || !button) return;
        if (DOM.imageModal.style.display === 'flex' && DOM.modalImageContent.src === button.closest('.journal-image-wrapper').querySelector('img').src) closeModal();
        const { safeSymbol, timeframe, id, filename } = button.dataset;
        if (confirm(`Delete this image?\n\n${filename}`)) {
            const storagePath = `journal_images/${safeSymbol}/${timeframe}/${filename}`;
            const dbPath = `${CONFIG.DB_PATHS.JOURNAL_IMAGES}/${safeSymbol}/${timeframe}/${id}`;
            storage.ref(storagePath).delete().then(() => database.ref(dbPath).remove()).catch((err) => { if (err.code === 'storage/object-not-found') database.ref(dbPath).remove(); });
        }
    }

    function handleFavouriteClick() {
        if (!STATE.isMasterUser) return;
        const safeSymbol = getSafeSymbol(DOM.journalSymbolEl.value), timeframe = DOM.journalTimeframeEl.value;
        const currentText = DOM.journalEntryEl.value.trim();
        const dbFavouriteRef = dbRefs.favourites.child(safeSymbol).child(timeframe);
        if (DOM.favouriteBtn.classList.contains('active')) dbFavouriteRef.remove();
        else { if (!currentText) return alert('Cannot pin an empty note.'); dbFavouriteRef.set(currentText); }
    }

    function resetMergeState() {
        STATE.isMerging = false; STATE.mergeBaseTradeId = null;
        document.body.classList.remove('in-merge-mode');
        document.querySelectorAll('#completed-trades-tbody tr.is-merge-base').forEach(row => row.classList.remove('is-merge-base'));
    }

    function initiateMerge(baseTradeId) {
        if (STATE.isMerging && STATE.mergeBaseTradeId === baseTradeId) { resetMergeState(); alert('Merge cancelled.'); return; }
        resetMergeState(); STATE.isMerging = true; STATE.mergeBaseTradeId = baseTradeId;
        document.body.classList.add('in-merge-mode');
        const baseRow = document.querySelector(`#completed-trades-tbody button[data-id='${baseTradeId}']`).closest('tr');
        if (baseRow) baseRow.classList.add('is-merge-base');
        alert('MERGE MODE: Click another trade to merge into this one. Click "Merge" again to cancel.');
    }

    function executeMerge(baseTradeId, absorbedTradeId) {
        if (!baseTradeId || !absorbedTradeId || baseTradeId === absorbedTradeId) { resetMergeState(); return; }
        const completedTradesRef = dbRefs.completedTrades;
        completedTradesRef.once('value', snapshot => {
            const allTrades = snapshot.val(), baseTrade = allTrades[baseTradeId], absorbedTrade = allTrades[absorbedTradeId];
            if (!baseTrade || !absorbedTrade) { alert('Error: Could not find one of the trades.'); resetMergeState(); return; }
            if (baseTrade.symbol !== absorbedTrade.symbol || baseTrade.type !== absorbedTrade.type) { alert('Error: Cannot merge trades with different symbols or types.'); resetMergeState(); return; }
            const baseSize = parseFloat(baseTrade.size), baseEntry = parseFloat(baseTrade.entry), baseQty = baseSize / baseEntry;
            const absorbedSize = parseFloat(absorbedTrade.size), absorbedEntry = parseFloat(absorbedTrade.entry), absorbedQty = absorbedSize / absorbedEntry;
            const totalQty = baseQty + absorbedQty, totalValue = baseSize + absorbedSize;
            const mergedEntry = totalValue / totalQty;
            const baseExitValue = parseFloat(baseTrade.exit_price) * baseQty, absorbedExitValue = parseFloat(absorbedTrade.exit_price) * absorbedQty;
            const mergedExitPrice = (baseExitValue + absorbedExitValue) / totalQty;
            const mergedEntryPrices = [...(baseTrade.entry_prices || [baseTrade.entry]), ...(absorbedTrade.entry_prices || [absorbedTrade.entry])];
            const mergedTrade = {
                ...baseTrade, entry: mergedEntry, size: totalValue, exit_price: mergedExitPrice, entry_prices: mergedEntryPrices,
                net_result: (baseTrade.net_result || 0) + (absorbedTrade.net_result || 0),
                entry_fee: (baseTrade.entry_fee || 0) + (absorbedTrade.entry_fee || 0),
                exit_fee: (baseTrade.exit_fee || 0) + (absorbedTrade.exit_fee || 0),
                date: Math.min(new Date(baseTrade.date).getTime(), new Date(absorbedTrade.date).getTime()),
                closed_date: Math.max(new Date(baseTrade.closed_date).getTime(), new Date(absorbedTrade.closed_date).getTime()),
                note: `${baseTrade.note || ''}\n--- MERGED ---\n${absorbedTrade.note || ''}`.trim(),
            };
            const updates = { [baseTradeId]: mergedTrade, [absorbedTradeId]: null };
            completedTradesRef.update(updates).then(() => { alert('Trades merged successfully!'); resetMergeState(); }).catch(e => { alert(`Error merging trades: ${e.message}`); resetMergeState(); });
        });
    }

    function subscribeToData() {
        dbRefs.trades.on('value', s => { const trades = s.val() || {}; renderLiveTable(trades); DOM.statOpenTrades.textContent = Object.keys(trades).length; });
        dbRefs.completedTrades.on('value', s => {
            const completedData = s.val() || {}; renderCompletedTable(completedData);
            let wins = 0, losses = 0, grossProfit = 0, grossLoss = 0;
            Object.values(completedData).forEach(trade => {
                const netResult = trade.net_result || 0;
                if (netResult > 0) { wins++; grossProfit += netResult; } else { losses++; grossLoss += Math.abs(netResult); }
            });
            const totalCompleted = wins + losses, winRate = totalCompleted > 0 ? (wins / totalCompleted) * 100 : 0;
            const profitFactor = grossLoss > 0 ? grossProfit / grossLoss : 0, avgWin = wins > 0 ? grossProfit / wins : 0;
            const avgLoss = losses > 0 ? grossLoss / losses : 0, rewardRisk = avgLoss > 0 ? avgWin / avgLoss : 0;
            const totalPL = grossProfit - grossLoss, newBalance = CONFIG.TRADE_SETTINGS.STARTING_BALANCE + totalPL;
            DOM.statBalance.textContent = formatCurrency(newBalance); DOM.statBalanceAud.textContent = formatCurrency(newBalance * STATE.usdToAudRate, 'A$');
            DOM.statTotalPl.textContent = `${totalPL >= 0 ? '+' : ''}${formatCurrency(totalPL)}`; DOM.statTotalPl.style.color = totalPL >= 0 ? 'var(--green-text)' : 'var(--red-text)';
            DOM.statTotalPlAud.textContent = `${totalPL >= 0 ? '+' : ''}${formatCurrency(totalPL * STATE.usdToAudRate, 'A$')}`; DOM.statTotalPlAud.style.color = totalPL >= 0 ? 'var(--green-text)' : 'var(--red-text)';
            DOM.statCompletedTrades.textContent = totalCompleted; DOM.statWins.textContent = wins; DOM.statLosses.textContent = losses;
            DOM.statWinRate.textContent = `${winRate.toFixed(1)}%`; DOM.statProfitFactor.textContent = profitFactor > 0 ? profitFactor.toFixed(2) : (wins > 0 ? '∞' : 'N/A');
            DOM.statAvgWin.textContent = formatCurrency(avgWin); DOM.statAvgLoss.textContent = formatCurrency(avgLoss); DOM.statRewardRisk.textContent = rewardRisk > 0 ? `${rewardRisk.toFixed(2)} : 1` : 'N/A';
            dbRefs.bank.set({ currentBalance: newBalance });
        });
        dbRefs.journalText.on('value', (s) => { STATE.journalText = s.val() || {}; if (DOM.journalTab.classList.contains('active')) updateJournalView(); });
        dbRefs.journalImages.on('value', (s) => { STATE.journalImages = s.val() || {}; if (DOM.journalTab.classList.contains('active')) updateJournalView(); });
        dbRefs.imageLibrary.on('value', (s) => renderGenericImageLibrary(s.val(), DOM.imageLibraryContainer, 'image_library'));
        dbRefs.setupsImages.on('value', (s) => renderGenericImageLibrary(s.val(), DOM.setupsImageContainer, 'setups_images'));
        dbRefs.chartLibrary2.on('value', s => {
            STATE.chartLibrary2Data = s.val() || {};
            if (STATE.currentCl2Folder) renderFolderContents(STATE.currentCl2Folder); else renderChartLibrary2Folders();
            renderChartLibrary2Preview();
        });
        dbRefs.favourites.on('value', (s) => { STATE.favouriteEntries = s.val() || {}; if (DOM.journalTab.classList.contains('active')) updateJournalView(); });
        dbRefs.setups1.on('value', (s) => { STATE.setupsData1 = s.val() || {}; renderSetupsTable(DOM.setupsTable1, STATE.setupsData1, 'primary-setups-notes'); });
        dbRefs.setups2.on('value', (s) => { STATE.setupsData2 = s.val() || {}; renderSetupsTable(DOM.setupsTable2, STATE.setupsData2, 'secondary-setups-notes'); });
        dbRefs.persistentNotes.on('value', (s) => { 
            STATE.persistentNotes = s.val() || ''; 
            if (document.activeElement !== DOM.persistentNotesEl) {
                DOM.persistentNotesEl.value = STATE.persistentNotes;
            }
            adjustCollapsibleSize(DOM.persistentNotesEl);
        });
        dbRefs.trackerScratchpad.on('value', (s) => { 
            STATE.trackerScratchpadText = s.val() || ''; 
            if (document.activeElement !== DOM.trackerScratchpadEl) {
                DOM.trackerScratchpadEl.value = STATE.trackerScratchpadText;
            }
            adjustCollapsibleSize(DOM.trackerScratchpadEl);
        });
        dbRefs.sentimentReceipts.on('value', (s) => {
            STATE.allSentimentReceipts = s.val() || {};
            renderSentimentReceipts();
        });
        dbRefs.levelNotes.on('value', (s) => renderLevelNotes(s.val()));
        dbRefs.generalNotes.on('value', (s) => {
            STATE.generalNotes = s.val() || {};
            if (DOM.noteEditModal.style.display === 'none') {
                renderNotes(STATE.generalNotes);
            }
        });
    }

    // --- INITIALIZATION ---
    function openCollapsibleSection(sectionElement) {
        if (!sectionElement || sectionElement.classList.contains('is-open')) return;
        const content = sectionElement.querySelector('.collapsible-content');
        const toggleBtn = sectionElement.querySelector('.collapsible-toggle-btn');
        if (content && toggleBtn) {
            sectionElement.classList.add('is-open'); 
            toggleBtn.textContent = '−'; 
            toggleBtn.style.transform = 'rotate(180deg)';
            setTimeout(() => {
                content.style.maxHeight = content.scrollHeight + 'px';
            }, 50);
        }
    }

    function openDefaultSectionsInContainer(containerElement) {
        if (!containerElement) return;
        const sectionsToOpen = ['Levels', 'Live Trades', 'Sentiment Log', 'Completed Trades', 'Setups', 'Trading Setups', 'Add New Trade', 'Notes', 'My Notes', 'Charts', 'Misc', 'Persistent Notes'];
        
        containerElement.querySelectorAll('.collapsible-header h2').forEach(h2 => {
            const title = h2.textContent.trim();
            if (sectionsToOpen.includes(title)) {
                const section = h2.closest('.collapsible-section');
                if (section && !(section.classList.contains('master-only') && !STATE.isMasterUser)) {
                    openCollapsibleSection(section);
                }
            }
        });
    }

    function checkMasterMode() {
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('master') === 'true') {
            const password = prompt("Please enter master password:");
            if (password) {
                STATE.isMasterUser = true; STATE.masterPassword = password;
                document.querySelectorAll('.master-only').forEach(el => {
                   if (el.classList.contains('collapsible-section') || el.id === 'favourite-btn' || el.classList.contains('sentiment-tracker')) {
                       el.style.display = 'block';
                   } else if (el.tagName === 'TH' || el.tagName === 'TD') {
                       el.style.display = 'table-cell';
                   } else if (el.id.startsWith('save-setups-')) {
                       el.style.display = 'inline-block';
                   } else {
                       el.style.display = 'block';
                   }
                });
                DOM.journalEntryEl.readOnly = false; DOM.persistentNotesEl.readOnly = false; DOM.trackerScratchpadEl.readOnly = false;
                document.querySelectorAll('.setups-table .editable-setup-cell').forEach(cell => cell.setAttribute('contenteditable', 'true'));
                DOM.primarySetupsNotes.readOnly = false; DOM.secondarySetupsNotes.readOnly = false;
            }
        }
        if (!STATE.isMasterUser) {
            DOM.journalEntryEl.readOnly = true; DOM.persistentNotesEl.readOnly = true; DOM.trackerScratchpadEl.readOnly = true;
            DOM.primarySetupsNotes.readOnly = true; DOM.secondarySetupsNotes.readOnly = true;
        }

        document.querySelectorAll('.key-open-note').forEach(input => {
            input.readOnly = !STATE.isMasterUser;
            if (!STATE.isMasterUser) {
                input.style.cursor = 'not-allowed';
                input.style.backgroundColor = 'transparent';
            }
        });
    }

    async function initializeApp() {
        checkMasterMode(); 
        getViewerId();
        await fetchLiveConversionRate();
        fetchEmaData();
        fetchSrData();
        fetchMarketOpens();
        fetchCrossoverSignalData();
        fetchAndRenderOptionsData();

        setInterval(fetchCrossoverSignalData, 5 * 60 * 1000); // Refresh every 5 minutes
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme) { 
            document.documentElement.setAttribute('data-theme', savedTheme); 
            DOM.themeToggle.checked = savedTheme === 'dark'; 
        }
        const today = new Date(); 
        today.setUTCHours(0, 0, 0, 0);
        STATE.selectedDate = new Date(today); 
        STATE.centerDate = new Date(today);
        setupEventListeners(); 
        subscribeToData();
        renderDateNavigation(); 
        renderChartLibrary2Folders(); 
        renderChartLibrary2Preview();

        const activeTabContent = document.querySelector('.tab-content.active');
        if (activeTabContent) {
            openDefaultSectionsInContainer(activeTabContent);
            activeTabContent.dataset.sectionsInitialized = 'true';
        }
    }

    initializeApp();
});
```
