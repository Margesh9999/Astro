# AstroTrader Frontend

## Overview
This is the frontend component of the AstroTrader project, built with Next.js and React. It provides an interactive dashboard for visualizing planetary positions, market data, and analysis results.

## Installation

### Prerequisites
- Node.js 18+
- npm (Node package manager)

### Setup
```bash
# Navigate to frontend directory
cd /c/Users/JaySh/AstroTrader/frontend

# Install dependencies
npm install
```

## Usage

### Start Development Server
```bash
npm run dev
```

The frontend will be available at http://localhost:3000

### Build for Production
```bash
npm run build
```

### Start Production Server
```bash
npm start
```

## Configuration
Create a `.env.local` file in the frontend directory with the following variables:

```
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

## Project Structure
```
frontend/
├── src/
│   ├── app/                    # Next.js app router
│   │   ├── layout.tsx          # Root layout
│   │   ├── page.tsx            # Home page
│   │   └── globals.css         # Global styles
│   ├── components/             # React components
│   │   ├── Header.tsx          # Site header
│   │   ├── Dashboard.tsx       # Main dashboard layout
│   │   ├── PlanetaryChart.tsx  # Planetary positions visualization
│   │   ├── MarketOverlay.tsx   # Market data display
│   │   ├── CorrelationHeatmap.tsx # Feature correlations
│   │   ├── PredictionTimeline.tsx # Market predictions
│   │   ├── BacktestResults.tsx # Backtesting results
│   │   └── EventsCalendar.tsx  # Astrological events calendar
│   ├── lib/                    # Utility files
│   │   ├── types.ts            # TypeScript interfaces
│   │   └── api.ts              # API service client
│   └── ...                     # Other src files
├── public/                     # Static assets
├── package.json                # Dependencies and scripts
├── next.config.js              # Next.js configuration
├── tsconfig.json               # TypeScript configuration
└── ...                         # Other config files
```

## Educational Purpose Only
**⚠️ IMPORTANT**: This frontend is for educational purposes only. It visualizes simulated data and should not be used for making financial decisions. Always consult with qualified financial professionals before making investment decisions.

## Technologies Used
- **Next.js 15** - React framework for server-rendered applications
- **React 19** - JavaScript library for building user interfaces
- **TypeScript** - Typed superset of JavaScript
- **Recharts** - Charting library built on React and D3
- **Axios** - HTTP client for making API requests

## License
MIT License