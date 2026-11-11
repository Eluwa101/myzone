import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
// Subset-specific imports (not the full "400.css" etc.) - this app is
// English/Latin-script only, so the Cyrillic/Greek/Vietnamese @font-face
// declarations in the full files are dead weight on every page load.
import "@fontsource/inter/latin-400.css";
import "@fontsource/inter/latin-500.css";
import "@fontsource/inter/latin-600.css";
import "@fontsource/inter/latin-700.css";
import "@fontsource/inter/latin-ext-400.css";
import "@fontsource/inter/latin-ext-500.css";
import "@fontsource/inter/latin-ext-600.css";
import "@fontsource/inter/latin-ext-700.css";
import "./index.css";
import App from "./App.tsx";
import { AuthProvider } from "./context/AuthContext";
import { NavigationHistoryProvider } from "./context/NavigationHistoryContext";
import { applyTheme, getStoredTheme } from "./utils/theme";

applyTheme(getStoredTheme());

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <NavigationHistoryProvider>
        <AuthProvider>
          <App />
        </AuthProvider>
      </NavigationHistoryProvider>
    </BrowserRouter>
  </StrictMode>,
);
