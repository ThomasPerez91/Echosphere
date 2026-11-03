// UX03 prototype entry (frontend/prototype/index.html). Never imported by src/main.tsx: the
// production build (`vite build`, input index.html) does not contain the prototype or its fixtures.
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "../style.css";
import "../command/command.css";
import "./prototype.css";
import { PrototypeApp } from "./PrototypeApp";

createRoot(document.getElementById("root")!).render(<StrictMode><PrototypeApp /></StrictMode>);
