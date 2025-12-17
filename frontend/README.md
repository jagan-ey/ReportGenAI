# GenAI CCM Platform - React Frontend

Simple React frontend for the GenAI-based Continuous Controls Monitoring platform.

## 🚀 Quick Start

### Prerequisites
- Node.js 18+ installed
- Backend server running on `http://localhost:8000`

### Installation

```bash
cd frontend
npm install
```

### Run Development Server

```bash
npm run dev
```

The app will open at `http://localhost:3000`

## 📁 Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── ChatInterface.jsx      # Main chat UI
│   │   ├── ChatInterface.css
│   │   ├── PredefinedQueries.jsx   # Sidebar with predefined queries
│   │   └── PredefinedQueries.css
│   ├── services/
│   │   └── api.js                  # API service for backend calls
│   ├── App.jsx                     # Main app component
│   ├── App.css
│   ├── main.jsx                    # Entry point
│   └── index.css                   # Global styles
├── index.html
├── vite.config.js
└── package.json
```

## 🎨 Features

- **Chat Interface**: Natural language query interface
- **Predefined Queries**: Sidebar with 7 predefined control questions
- **SQL Query Display**: View generated SQL queries
- **Real-time Responses**: Instant feedback from backend
- **Responsive Design**: Works on desktop and mobile

## 🔧 Configuration

The API base URL is configured in `src/services/api.js`. Default is `http://localhost:8000/api`.

To change it, edit:
```javascript
const API_BASE_URL = 'http://localhost:8000/api'
```

## 📦 Build for Production

```bash
npm run build
```

Output will be in the `dist/` directory.

## 🐛 Troubleshooting

**CORS Errors**: Make sure the backend CORS settings allow `http://localhost:3000`

**Connection Errors**: Ensure the backend server is running on port 8000

**Module Not Found**: Run `npm install` to install dependencies

