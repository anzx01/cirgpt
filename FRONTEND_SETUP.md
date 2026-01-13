# Frontend Setup and Usage Guide

## Overview

The frontend is **100% complete** with all UI components implemented! This includes:

✅ Design interface with natural language input
✅ Real-time progress tracking via Socket.io
✅ Schematic viewer using SVG.js
✅ Simulation results viewer with Recharts
✅ PCB viewer with zoom controls
✅ BOM table with CSV export
✅ Responsive Material-UI design

## Frontend Architecture

```
frontend/
├── app/
│   ├── page.jsx                    # Landing page (updated)
│   ├── layout.jsx                  # Layout with navigation
│   ├── design/
│   │   ├── page.jsx               # Design input form
│   │   └── [id]/
│   │       └── page.jsx           # Results display with real-time updates
│   └── globals.css                # Global styles
│
├── components/
│   ├── NavigationBar.tsx           # Navigation bar
│   ├── SchematicViewer.jsx        # SVG schematic viewer
│   ├── SimulationViewer.jsx       # Waveform charts (Recharts)
│   ├── PcbViewer.jsx              # PCB layout viewer
│   └── BomViewer.jsx              # BOM table with export
│
└── package.json                   # Dependencies
```

## Pages and Routes

### 1. Home Page (`/`)
**File:** `app/page.jsx`

**Features:**
- Hero section with gradient title
- Feature cards (AI Design, Automatic Schematics, Smart PCB)
- "How It Works" section (3 steps)
- Call-to-action section
- Responsive Material-UI layout

**Navigation:** Click "Start Designing Now" button → goes to `/design`

---

### 2. Design Input Page (`/design`)
**File:** `app/design/page.jsx`

**Features:**
- Large textarea for natural language input
- Example prompts (clickable chips):
  - 555 timer LED blinker
  - Inverting amplifier with gain 10
  - Power supply design
  - Low-pass RC filter
- Submit button with loading state
- Error handling

**API Calls:**
```javascript
POST /api/circuit/  → Create design
POST /api/circuit/{id}/generate  → Start generation
```

**User Flow:**
1. User enters description
2. Clicks "Generate Circuit"
3. Design created in database
4. Generation started in background
5. Redirects to `/design/{id}`

---

### 3. Results Page (`/design/{id}`)
**File:** `app/design/[id]/page.jsx`

**Features:**
- **Progress tracking:**
  - Linear progress bar
  - Real-time status updates (Socket.io)
  - Progress percentage display

- **Tabbed interface:**
  - Tab 1: Schematic (SVG.js)
  - Tab 2: Simulation (Recharts)
  - Tab 3: PCB Layout
  - Tab 4: Bill of Materials

- **Actions:**
  - Create New Design button
  - Estimated cost display

**Socket.io Integration:**
```javascript
// Connect to server
const socket = io('http://localhost:8000');

// Subscribe to design updates
socket.emit('subscribe', { design_id: id });

// Listen for progress
socket.on('design_progress', (data) => {
  // Update progress bar
});

// Listen for completion
socket.on('design_complete', () => {
  // Reload design data
});

// Listen for errors
socket.on('design_error', (error) => {
  // Show error message
});
```

---

## Components

### 1. SchematicViewer (`components/SchematicViewer.jsx`)

**Purpose:** Display SVG schematics with interactive controls

**Features:**
- SVG.js rendering
- Zoom in/out (40% - 300%)
- Download as SVG
- Responsive container

**Props:**
```javascript
{
  svg: string  // SVG markup from backend
}
```

**Usage:**
```jsx
<SchematicViewer svg={design.schematic_svg} />
```

---

### 2. SimulationViewer (`components/SimulationViewer.jsx`)

**Purpose:** Display simulation waveforms and statistics

**Features:**
- **Statistics cards:**
  - Max/Min/Avg voltage
  - Peak-to-peak voltage
  - Frequency

- **Voltage waveform chart:**
  - Output voltage (blue line)
  - Input voltage (orange line, if available)

- **Current waveform chart:**
  - Current in mA (green line)

- **Recharts integration:**
  - Responsive line charts
  - Tooltips
  - Legends
  - Axis labels

**Props:**
```javascript
{
  results: {
    time: number[],
    voltages: {
      output: number[],
      input: number[]
    },
    currents: {
      total: number[]
    },
    summary: {
      estimated_frequency: number
    }
  }
}
```

---

### 3. PcbViewer (`components/PcbViewer.jsx`)

**Purpose:** Display PCB layout visualization

**Features:**
- PCB image display (base64 PNG)
- Zoom controls
- Fullscreen mode
- Download as PNG
- Board information:
  - Dimensions
  - Layers
  - Component count
  - Track count

**Props:**
```javascript
{
  layout: {
    dimensions: { width, height },
    layers: number,
    components: array
  },
  image: string  // Base64 PNG
}
```

---

### 4. BomViewer (`components/BomViewer.jsx`)

**Purpose:** Display bill of materials with export

**Features:**
- **Summary cards:**
  - Total components
  - Unique components
  - Total cost

- **Component table:**
  - Designator
  - Quantity
  - Component type
  - Value
  - Footprint
  - Unit price
  - Total price
  - Supplier
  - Part number

- **Cost breakdown by component type**

- **CSV download:** Click button to download BOM

**Props:**
```javascript
{
  bom: {
    entries: array,
    summary: {
      total_components: number,
      unique_components: number,
      total_cost: number
    },
    csv: string,
    design_name: string
  }
}
```

---

## Setup Instructions

### 1. Install Dependencies

```bash
cd frontend
npm install
```

**Required packages (from package.json):**
```json
{
  "next": "^14.2.3",
  "react": "^18.2.0",
  "@mui/material": "^5.15.0",
  "@mui/icons-material": "^5.15.0",
  "@emotion/react": "^11.11.0",
  "socket.io-client": "^4.6.0",
  "@svgdotjs/svg.js": "^3.2.0",
  "axios": "^1.6.0",
  "recharts": "^2.10.0"
}
```

### 2. Start Development Server

```bash
npm run dev
```

Frontend will run on `http://localhost:3000`

### 3. Environment Variables

Create `.env.local` in the frontend directory:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SOCKET_URL=http://localhost:8000
```

---

## User Flow Walkthrough

### Complete User Journey

1. **Landing Page (`/`)**
   - User sees hero section with "Start Designing Now" button
   - Clicks button → navigates to `/design`

2. **Design Input (`/design`)**
   - User sees large textarea
   - User types: "Design a 555 timer LED blinker circuit with 1 Hz frequency"
   - User clicks "Generate Circuit"

3. **Generation Starts**
   - Frontend calls `POST /api/circuit/` → creates design (ID: 1)
   - Frontend calls `POST /api/circuit/1/generate` → starts background task
   - Frontend redirects to `/design/1`

4. **Results Page (`/design/1`) - Processing**
   - Socket.io connects to server
   - Subscribes to design updates
   - Progress bar updates in real-time:
     - 10%: "Parsing natural language"
     - 30%: "Generating netlist"
     - 50%: "Generating schematic"
     - 70%: "Running simulation"
     - 85%: "Generating PCB"
     - 95%: "Generating BOM"
     - 100%: "Design generation complete!"

5. **Results Page - Completed**
   - Progress bar shows 100%
   - Success alert displayed
   - Tabs become enabled

6. **View Results**
   - **Schematic tab:** Shows SVG with zoom controls
   - **Simulation tab:** Shows voltage/current waveforms
   - **PCB tab:** Shows PCB layout image
   - **BOM tab:** Shows component table with CSV download

7. **Download/Export**
   - Download schematic as SVG
   - Download PCB as PNG
   - Download BOM as CSV

8. **Next Actions**
   - Click "Create New Design" → goes back to `/design`
   - Start over with new description

---

## Socket.io Events

### Client → Server Events

| Event | Payload | Description |
|-------|---------|-------------|
| `subscribe` | `{design_id: int}` | Subscribe to design updates |
| `unsubscribe` | `{design_id: int}` | Unsubscribe from updates |

### Server → Client Events

| Event | Payload | Description |
|-------|---------|-------------|
| `connected` | `{message: string}` | Connection confirmation |
| `design_status` | `{design_id, status, progress, message}` | Current status |
| `design_progress` | `{design_id, message, progress, timestamp}` | Progress update |
| `design_complete` | `{design_id}` | Generation complete |
| `design_error` | `{design_id, error}` | Error occurred |

---

## Responsive Design

All pages and components are fully responsive:

**Breakpoints:**
- Mobile: `< 600px`
- Tablet: `600px - 900px`
- Desktop: `> 900px`

**Adaptations:**
- Cards stack vertically on mobile
- Tables scroll horizontally
- Charts resize automatically
- Navigation becomes drawer on mobile

---

## Styling

**Theme:** Material-UI default theme with customizations

**Colors:**
- Primary: Blue (#1976d2)
- Secondary: Orange
- Success: Green
- PCB Green: (#2e7d32)

**Typography:**
- Headings: Roboto Bold
- Body: Roboto Regular
- Monospace for part numbers

---

## Error Handling

**Design Input Page:**
- Empty input → Error alert
- API failure → Error alert with retry option
- Network error → User-friendly message

**Results Page:**
- Generation failed → Error alert + "Create New Design" button
- Socket.io disconnect → Auto-reconnect
- Missing data → Graceful fallback with info message

---

## Performance Optimizations

1. **Lazy loading:** Components load only when needed
2. **Memoization:** Chart data cached with `useMemo`
3. **Debouncing:** Socket.io updates throttled
4. **Image optimization:** PCB images compressed
5. **Code splitting:** Automatic with Next.js

---

## Testing Checklist

### Manual Testing Steps

1. **Landing Page**
   - [ ] All buttons work
   - [ ] Responsive on mobile/tablet/desktop
   - [ ] Navigation to design page works

2. **Design Input**
   - [ ] Can type in textarea
   - [ ] Example prompts work
   - [ ] Submit button creates design
   - [ ] Redirect to results page

3. **Results Page - During Generation**
   - [ ] Socket.io connects successfully
   - [ ] Progress bar updates in real-time
   - [ ] Progress messages display correctly
   - [ ] Tabs are disabled during processing

4. **Results Page - After Generation**
   - [ ] Tabs become enabled
   - [ ] Schematic displays correctly
   - [ ] Simulation charts render
   - [ ] PCB viewer shows image
   - [ ] BOM table populates
   - [ ] Export buttons work

5. **Component Testing**
   - [ ] Schematic zoom in/out works
   - [ ] Simulation charts interactive
   - [ ] PCB fullscreen works
   - [ ] BOM CSV downloads correctly

---

## Troubleshooting

### Issue: "Socket.io connection failed"

**Solution:**
- Check backend is running on port 8000
- Check CORS settings in backend
- Check firewall settings

### Issue: "Charts not rendering"

**Solution:**
- Check Recharts is installed
- Check data format is correct
- Check browser console for errors

### Issue: "SVG not displaying"

**Solution:**
- Check SVG.js is installed
- Check SVG markup is valid
- Check container has proper dimensions

### Issue: "Export buttons not working"

**Solution:**
- Check data is available
- Check browser download permissions
- Check file extension is correct

---

## Deployment

### Build for Production

```bash
cd frontend
npm run build
```

### Start Production Server

```bash
npm start
```

### Environment Variables for Production

```env
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
NEXT_PUBLIC_SOCKET_URL=https://api.yourdomain.com
NODE_ENV=production
```

---

## Summary

✅ **Frontend Implementation: 100% Complete**

All components are implemented and ready for testing:
- Modern, responsive UI with Material-UI
- Real-time updates via Socket.io
- Interactive visualizations (SVG.js, Recharts)
- Export functionality (SVG, PNG, CSV)
- Error handling and loading states
- Mobile-responsive design

**Ready for end-to-end testing!**
