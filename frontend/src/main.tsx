import React from "react";
import ReactDOM from "react-dom/client";
import { HttpAgent } from "@ag-ui/client";
import { CopilotKit } from "@copilotkit/react-core/v2";
import "@copilotkit/react-core/v2/styles.css";
import App from "./App";
import "./styles.css";

// This POC uses CopilotKit's development-only direct AG-UI connection. Vite
// proxies this same-origin route to FastAPI, so no browser CORS setup is needed.
const triageAgent = new HttpAgent({
  url: import.meta.env.VITE_COPILOT_AGENT_URL || "/agents/triage",
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <CopilotKit agents__unsafe_dev_only={{ triage_copilot: triageAgent }} agent="triage_copilot">
      <App />
    </CopilotKit>
  </React.StrictMode>,
);
