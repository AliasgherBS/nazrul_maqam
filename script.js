// API Base URL - Update this to match your actual backend server
// const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' 
//     ? `${window.location.protocol}//${window.location.hostname}:8000/api` 
//     : 'http://localhost:8000/api';

const API_BASE_URL = 'https://nazrulmaqam-production.up.railway.app/api';

    // DOM Elements
document.addEventListener('DOMContentLoaded', () => {
    // Summary Elements
    const totalAllTimeEl = document.getElementById('total-all-time');
    const totalThisMonthEl = document.getElementById('total-this-month');
    const totalThisYearEl = document.getElementById('total-this-year');
    
    // Settings Elements
    const currentDailyAmountEl = document.getElementById('current-daily-amount');
    const showChangeSettingsBtn = document.getElementById('show-change-settings');
    const changeAmountForm = document.getElementById('change-amount-form');
    const dailyAmountInput = document.getElementById('daily-amount');
    const saveSettingsBtn = document.getElementById('save-settings');
    const cancelSettingsBtn = document.getElementById('cancel-settings');
    
    // Donation Form Elements
    const donationForm = document.getElementById('donation-form');
    const donationAmountInput = document.getElementById('donation-amount');
    const donationDateInput = document.getElementById('donation-date');
    const donationCommentInput = document.getElementById('donation-comment');
    
    // History Filter Elements
    const startDateInput = document.getElementById('start-date');
    const endDateInput = document.getElementById('end-date');
    const filterButton = document.getElementById('filter-button');
    const resetFilterButton = document.getElementById('reset-filter');
    const donationListEl = document.getElementById('donation-list');
    
    // Chart Element
    const donationChartEl = document.getElementById('donation-chart');
    let donationChart = null;
    
    // Set default date values
    const today = new Date();
    donationDateInput.value = formatDate(today);
    
    // Initialize the app
    initApp();
    
    // Event Listeners
    showChangeSettingsBtn.addEventListener('click', () => {
        changeAmountForm.classList.remove('hidden');
    });
    
    cancelSettingsBtn.addEventListener('click', () => {
        changeAmountForm.classList.add('hidden');
        // Reset the input to current value
        loadUserSettings();
    });
    
    saveSettingsBtn.addEventListener('click', saveSettings);
    donationForm.addEventListener('submit', handleDonationSubmit);
    filterButton.addEventListener('click', filterDonations);
    resetFilterButton.addEventListener('click', resetFilters);
    
    // Functions
    
    // Run auto-donate silently (without UI feedback)
    async function runAutoDonateSilently() {
        try {
            console.log("Running auto-donate silently on page load...");
            const response = await fetch(`${API_BASE_URL}/auto-donate`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            if (!response.ok) {
                throw new Error(`Auto-donate failed: ${response.statusText}`);
            }
            
            const result = await response.json();
            console.log(`Auto-donate result: ${result.message} (${result.count} donations added)`);
            
            // Don't show UI feedback, but return the result
            return result;
        } catch (error) {
            console.error('Error running auto-donate silently:', error);
            // Silently fail - don't show alert to user
            return null;
        }
    }
    
    // Event Listeners
    showChangeSettingsBtn.addEventListener('click', () => {
        changeAmountForm.classList.remove('hidden');
    });
    
    cancelSettingsBtn.addEventListener('click', () => {
        changeAmountForm.classList.add('hidden');
        // Reset the input to current value
        loadUserSettings();
    });
    
    saveSettingsBtn.addEventListener('click', saveSettings);
    donationForm.addEventListener('submit', handleDonationSubmit);
    filterButton.addEventListener('click', filterDonations);
    resetFilterButton.addEventListener('click', resetFilters);
    
    // Functions
    
    // Initialize the app
    async function initApp() {
        try {
            // Test backend connection first
            const testResponse = await fetch(`${API_BASE_URL}/user`, { 
                method: 'GET',
                headers: {
                    'Accept': 'application/json',
                    'Content-Type': 'application/json'
                },
                // Add a timeout to avoid long hanging requests
                signal: AbortSignal.timeout(5000)  
            });
            
            if (!testResponse.ok) {
                throw new Error(`Server returned ${testResponse.status}: ${testResponse.statusText}`);
            }
            
            // If we get here, connection is good
            console.log("Connection to server established successfully");
            
            // Load user settings
            await loadUserSettings();
            
            // Auto-donate (run silently on page load)
            await runAutoDonateSilently();
            
            // Load summary data
            await loadSummary();
            
            // Load donation history
            await loadDonations();
            
            // Initialize chart
            await initChart();
        } catch (error) {
            console.error('Error initializing app:', error);
            const message = error.name === 'AbortError' 
                ? 'Connection to server timed out. Please check if the server is running at the correct address.'
                : `Failed to connect to server: ${error.message}. Please verify the server is running at ${API_BASE_URL}`;
            displayErrorMessage(message);
        }
    }
    
    // Load user settings
    async function loadUserSettings() {
        try {
            const response = await fetch(`${API_BASE_URL}/user`);
            if (!response.ok) {
                throw new Error(`Failed to load user settings: ${response.statusText}`);
            }
            
            const user = await response.json();
            dailyAmountInput.value = user.daily_amount;
            currentDailyAmountEl.textContent = formatCurrency(user.daily_amount);
            console.log("User settings loaded successfully");
        } catch (error) {
            console.error('Error loading user settings:', error);
            throw error;
        }
    }
    
    // Save user settings
    async function saveSettings() {
        const dailyAmount = parseFloat(dailyAmountInput.value);
        
        if (isNaN(dailyAmount) || dailyAmount < 0) {
            alert('Please enter a valid daily amount (must be 0 or greater)');
            return;
        }
        
        try {
            const response = await fetch(`${API_BASE_URL}/user/settings`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    daily_amount: dailyAmount
                })
            });
            
            if (!response.ok) {
                throw new Error(`Failed to save settings: ${response.statusText}`);
            }
            
            const user = await response.json();
            currentDailyAmountEl.textContent = formatCurrency(user.daily_amount);
            changeAmountForm.classList.add('hidden');
            // alert('Settings saved successfully!');
        } catch (error) {
            console.error('Error saving settings:', error);
            alert('Failed to save settings. Please try again.');
        }
    }
    
    // Handle donation form submission
    async function handleDonationSubmit(e) {
        e.preventDefault();
        
        const amount = parseFloat(donationAmountInput.value);
        const date = donationDateInput.value;
        const comment = donationCommentInput.value.trim();
        
        if (isNaN(amount) || amount <= 0) {
            alert('Please enter a valid amount (must be greater than 0)');
            return;
        }
        
        console.log(`Submitting donation: amount=${amount}, date=${date}, comment=${comment || "none"}`);
        
        try {
            // Debug output
            console.log("Sending JSON:", JSON.stringify({
                amount: amount,
                date: date,
                is_automatic: false,
                comment: comment || null
            }));
            
            const response = await fetch(`${API_BASE_URL}/donations`, {
                method: 'POST',
                headers: {
                    'Accept': 'application/json',
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    amount: amount,
                    date: date,
                    is_automatic: false,
                    comment: comment || null
                })
            });
            
            // Debug the response
            console.log("Response status:", response.status);
            console.log("Response headers:", [...response.headers.entries()]);
            
            // Get response text first for debugging
            const responseText = await response.text();
            console.log("Response text:", responseText);
            
            let responseData;
            try {
                // Try to parse as JSON if possible
                responseData = JSON.parse(responseText);
                console.log("Parsed JSON response:", responseData);
            } catch (jsonError) {
                console.error("Failed to parse response as JSON:", jsonError);
                if (!response.ok) {
                    throw new Error(responseText || `HTTP error: ${response.status}`);
                }
            }
            
            if (!response.ok) {
                // Handle FastAPI error response format
                if (responseData && responseData.detail) {
                    throw new Error(responseData.detail);
                } else {
                    throw new Error(`HTTP error: ${response.status}`);
                }
            }
            
            // Reset form
            donationAmountInput.value = '';
            donationCommentInput.value = '';
            
            // Reload data to reflect changes
            console.log("Donation added successfully, refreshing data...");
            await loadSummary();
            const donations = await loadDonations();
            
            // Update chart with new data
            if (donationChart) {
                updateDonationChart(donations);
            } else {
                createDonationChart(donations);
            }
            
            alert('Contribution added successfully!');
        } catch (error) {
            console.error('Error adding donation:', error);
            
            // Try to get a meaningful error message
            let errorMessage = error.message || 'Unknown error';
            if (errorMessage === '[object Object]') {
                errorMessage = 'Server returned an invalid response';
            }
            
            alert(`Failed to add Contribution: ${errorMessage}`);
        }
    }
    
    // Load summary data
    async function loadSummary() {
        try {
            const response = await fetch(`${API_BASE_URL}/donations/summary`);
            if (!response.ok) {
                throw new Error(`Failed to load summary: ${response.statusText}`);
            }
            
            const summary = await response.json();
            
            totalAllTimeEl.textContent = formatCurrency(summary.total_all_time);
            totalThisMonthEl.textContent = formatCurrency(summary.total_this_month);
            // totalThisYearEl.textContent = formatCurrency(summary.total_this_year);
            
            console.log("Summary data loaded successfully");
        } catch (error) {
            console.error('Error loading summary:', error);
            throw error;
        }
    }
    
    // Load donation history
    async function loadDonations(startDate = null, endDate = null) {
        try {
            let url = `${API_BASE_URL}/donations`;
            const params = new URLSearchParams();
            
            if (startDate) params.append('start_date', startDate);
            if (endDate) params.append('end_date', endDate);
            
            if (params.toString()) {
                url += `?${params.toString()}`;
            }
            
            console.log(`Fetching donations from: ${url}`);
            
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`Failed to load donations: ${response.statusText}`);
            }
            
            const donations = await response.json();
            console.log(`Loaded ${donations.length} donations`);
            
            renderDonationList(donations);
            return donations;
        } catch (error) {
            console.error('Error loading donations:', error);
            // Show empty state instead of failing
            renderDonationList([]);
            return [];
        }
    }
    
    // Initialize chart
    async function initChart() {
        try {
            const donations = await loadDonations();
            createDonationChart(donations);
            console.log("Chart initialized successfully");
        } catch (error) {
            console.error('Error initializing chart:', error);
            createDonationChart([]);
        }
    }

    // Create donation chart
    function createDonationChart(donations) {
        try {
            // Make sure we have a canvas element
            if (!donationChartEl) {
                console.error('Chart canvas element not found');
                return;
            }
            
            // Destroy existing chart if any
            if (donationChart) {
                donationChart.destroy();
                donationChart = null;
            }
            
            // Prepare data for chart - get last 30 days
            const chartData = prepareChartData(donations);
            
            // Create chart
            donationChart = new Chart(donationChartEl, {
                type: 'bar',
                data: {
                    labels: chartData.labels,
                    datasets: [{
                        label: 'Daily Donations (PKR)',
                        data: chartData.values,
                        backgroundColor: 'rgba(65, 164, 255, 0.7)',
                        borderColor: 'rgba(65, 164, 255, 1)',
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: 'Amount (PKR)'
                            }
                        },
                        x: {
                            title: {
                                display: true,
                                text: 'Date'
                            }
                        }
                    }
                }
            });
            
            console.log("Chart created successfully");
        } catch (error) {
            console.error('Error creating chart:', error);
        }
    }
    
    // Update donation chart
    function updateDonationChart(donations) {
        try {
            if (!donationChart) {
                createDonationChart(donations);
                return;
            }
            
            const chartData = prepareChartData(donations);
            
            donationChart.data.labels = chartData.labels;
            donationChart.data.datasets[0].data = chartData.values;
            donationChart.update();
            
            console.log("Chart updated successfully");
        } catch (error) {
            console.error('Error updating chart:', error);
            createDonationChart(donations);
        }
    }
    
    // Prepare chart data - get last 30 days
    function prepareChartData(donations) {
        // Create a map of dates to total amounts
        const donationsByDate = new Map();
        
        // Get date range - last 30 days
        const end = new Date();
        const start = new Date();
        start.setDate(end.getDate() - 29); // 30 days including today
        
        // Initialize all dates in range with zero amount
        for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
            donationsByDate.set(formatDate(d), 0);
        }
        
        // Sum donations by date
        donations.forEach(donation => {
            const date = donation.date.split('T')[0]; // YYYY-MM-DD format
            if (donationsByDate.has(date)) {
                donationsByDate.set(date, donationsByDate.get(date) + donation.amount);
            }
        });
        
        // Convert to arrays for chart
        const sortedDates = Array.from(donationsByDate.keys()).sort();
        const labels = sortedDates.map(date => {
            const d = new Date(date);
            return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        });
        const values = sortedDates.map(date => donationsByDate.get(date));
        
        return { labels, values };
    }
    
    // Filter donations
    function filterDonations() {
        const startDate = startDateInput.value;
        const endDate = endDateInput.value;
        
        if (!startDate && !endDate) {
            alert('Please select at least one date to filter');
            return;
        }
        
        loadDonations(startDate, endDate);
    }
    
    // Reset filters
    function resetFilters() {
        startDateInput.value = '';
        endDateInput.value = '';
        loadDonations();
    }
    
    // Render donation list
    function renderDonationList(donations) {
        donationListEl.innerHTML = '';
        
        if (donations.length === 0) {
            donationListEl.innerHTML = `
                <div class="donation-item placeholder">
                    <p>No contributions found for the selected period.</p>
                </div>
            `;
            return;
        }
        
        donations.forEach(donation => {
            const donationItem = document.createElement('div');
            donationItem.className = 'donation-item';
            
            const dateObj = new Date(donation.date);
            const formattedDate = dateObj.toLocaleDateString('en-US', { 
                weekday: 'short', 
                year: 'numeric', 
                month: 'short', 
                day: 'numeric' 
            });
            
            donationItem.innerHTML = `
                <div>
                    <div class="donation-date-amount">
                        ${formattedDate} - 
                        <span class="donation-amount">${formatCurrency(donation.amount)}</span>
                        ${donation.is_automatic ? '<span class="auto-tag">Auto</span>' : ''}
                    </div>
                    ${donation.comment ? `<div class="donation-comment">"${donation.comment}"</div>` : ''}
                </div>
                <div class="donation-meta">
                    ${new Date(donation.created_at).toLocaleTimeString()}
                </div>
            `;
            
            donationListEl.appendChild(donationItem);
        });
    }
    
    // Helper Functions
    
    // Format date to YYYY-MM-DD
    function formatDate(date) {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    }
    
    // Format currency for PKR
    function formatCurrency(amount) {
        return `${amount}/-`;
    }
    
    // Display error message
    function displayErrorMessage(message) {
        const errorDiv = document.createElement('div');
        errorDiv.style.backgroundColor = '#ffebee';
        errorDiv.style.color = '#c62828';
        errorDiv.style.padding = '10px';
        errorDiv.style.marginBottom = '20px';
        errorDiv.style.borderRadius = '4px';
        errorDiv.textContent = message;
        
        const container = document.querySelector('.container');
        container.insertBefore(errorDiv, container.firstChild);
    }
});