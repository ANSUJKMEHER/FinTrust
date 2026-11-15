import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from './context/ThemeContext';
import { AuthProvider } from './context/AuthContext';
import { Shell } from './components/layout/Shell';

// Pages
import { Dashboard } from './pages/Dashboard';
import { Research } from './pages/Research';
import { Investigations } from './pages/Investigations';
import { ComplianceAudit } from './pages/ComplianceAudit';
import { Documents } from './pages/Documents';
import { Upload } from './pages/Upload';
import { Comparison } from './pages/Comparison';
import { AgentExplorer } from './pages/AgentExplorer';
import { WorkflowHistory } from './pages/WorkflowHistory';
import { MCPActivity } from './pages/MCPActivity';
import { Approvals } from './pages/Approvals';
import { AuditLogs } from './pages/AuditLogs';
import { EvaluationStudio } from './pages/EvaluationStudio';
import { Settings } from './pages/Settings';

export const App: React.FC = () => {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Shell />}>
              <Route index element={<Dashboard />} />
              <Route path="overview" element={<Navigate to="/" replace />} />
              <Route path="research" element={<Research />} />
              <Route path="investigations" element={<Investigations />} />
              <Route path="compliance" element={<ComplianceAudit />} />
              <Route path="documents" element={<Documents />} />
              <Route path="upload" element={<Upload />} />
              <Route path="comparison" element={<Comparison />} />
              <Route path="agent-explorer" element={<AgentExplorer />} />
              <Route path="workflow-history" element={<WorkflowHistory />} />
              <Route path="mcp-activity" element={<MCPActivity />} />
              <Route path="approvals" element={<Approvals />} />
              <Route path="audit-logs" element={<AuditLogs />} />
              <Route path="evaluation" element={<EvaluationStudio />} />
              <Route path="settings" element={<Settings />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
};

export default App;
