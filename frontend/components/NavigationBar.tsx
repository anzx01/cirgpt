"use client"

import * as React from 'react'
import AppBar from '@mui/material/AppBar'
import Box from '@mui/material/Box'
import Toolbar from '@mui/material/Toolbar'
import Typography from '@mui/material/Typography'
import Button from '@mui/material/Button'
import IconButton from '@mui/material/IconButton'
import MenuIcon from '@mui/icons-material/Menu'
import Drawer from '@mui/material/Drawer'
import List from '@mui/material/List'
import ListItem from '@mui/material/ListItem'
import ListItemButton from '@mui/material/ListItemButton'
import ListItemIcon from '@mui/material/ListItemIcon'
import ListItemText from '@mui/material/ListItemText'
import DashboardIcon from '@mui/icons-material/Dashboard'
import EditIcon from '@mui/icons-material/Edit'
import FileCopyIcon from '@mui/icons-material/FileCopy'
import SettingsIcon from '@mui/icons-material/Settings'
import { useRouter } from 'next/navigation'

const menuItems = [
  { text: 'Workbench', icon: <DashboardIcon />, path: '/' },
  { text: 'New Design', icon: <EditIcon />, path: '/design' },
  { text: 'Templates', icon: <FileCopyIcon />, path: '/templates' },
  { text: 'Settings', icon: <SettingsIcon />, path: '/settings' },
]

const NavigationBar = () => {
  const router = useRouter()
  const [mobileOpen, setMobileOpen] = React.useState(false)

  const handleDrawerToggle = () => {
    setMobileOpen(!mobileOpen)
  }

  const drawer = (
    <Box sx={{ width: 250 }} role="presentation" onClick={handleDrawerToggle}>
      <Typography variant="h6" sx={{ padding: 2 }}>
        CircuitGPT
      </Typography>
      <List>
        {menuItems.map((item) => (
          <ListItem key={item.text} disablePadding>
            <ListItemButton onClick={() => router.push(item.path)}>
              <ListItemIcon>{item.icon}</ListItemIcon>
              <ListItemText primary={item.text} />
            </ListItemButton>
          </ListItem>
        ))}
      </List>
    </Box>
  )

  return (
    <Box sx={{ flexGrow: 1 }}>
      <AppBar position="static">
        <Toolbar>
          <IconButton
            size="large"
            edge="start"
            color="inherit"
            aria-label="menu"
            sx={{ mr: 2, display: { sm: 'none' } }}
            onClick={handleDrawerToggle}
          >
            <MenuIcon />
          </IconButton>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            CircuitGPT
          </Typography>
          <Box sx={{ display: { xs: 'none', sm: 'flex' }, gap: 1 }}>
            <Button color="inherit" onClick={() => router.push('/')}>
              Workbench
            </Button>
            <Button color="inherit" onClick={() => router.push('/design')}>
              New Design
            </Button>
          </Box>
        </Toolbar>
      </AppBar>
      <Box component="nav">
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={handleDrawerToggle}
          ModalProps={{ keepMounted: true }}
          sx={{
            display: { xs: 'block', sm: 'none' },
            '& .MuiDrawer-paper': { boxSizing: 'border-box', width: 250 },
          }}
        >
          {drawer}
        </Drawer>
      </Box>
    </Box>
  )
}

export default NavigationBar
