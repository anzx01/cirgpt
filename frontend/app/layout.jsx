import React from 'react'
import { Box, Container, Typography } from '@mui/material'
import NavigationBar from '../components/NavigationBar'
import ThemeRegistry from '../components/ThemeRegistry'

export default function RootLayout({ children }) {
  // suppressHydrationWarning on <html>: browser extensions (e.g. immersive
  // translate) inject data-* attributes onto <html> before React hydrates;
  // that attribute mismatch is not ours to patch up.
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>CircuitGPT</title>
      </head>
      <body>
        <ThemeRegistry>
          <NavigationBar />
          <main>{children}</main>
          <Box sx={{ bgcolor: 'primary.main', color: 'white', py: 3, mt: 4 }}>
            <Container maxWidth="lg">
              <Typography variant="body2" align="center">
                Copyright 2026 CircuitGPT contributors. Licensed under ISC.
              </Typography>
            </Container>
          </Box>
        </ThemeRegistry>
      </body>
    </html>
  )
}
