import { useState, useEffect } from 'react';
import { isSetupComplete, runFirstTimeSetup } from '../setup';
import './SetupScreen.css';

// Installation steps with descriptions
const INSTALLATION_STEPS = [
    { id: 1, name: 'Checking installation', status: 'pending' },
    { id: 2, name: 'Locating Python environment', status: 'pending' },
    { id: 3, name: 'Extracting Python packages (~300MB)', status: 'pending' },
    { id: 4, name: 'Installing OCR models', status: 'pending' },
    { id: 5, name: 'Verifying installation', status: 'pending' },
    { id: 6, name: 'Starting backend server', status: 'pending' },
];

export default function SetupScreen({ onSetupComplete }) {
    const [progress, setProgress] = useState(0);
    const [status, setStatus] = useState('Initializing...');
    const [error, setError] = useState(null);
    const [showTimeout, setShowTimeout] = useState(false);
    const [startTime] = useState(Date.now());
    const [elapsedTime, setElapsedTime] = useState(0);
    const [steps, setSteps] = useState(INSTALLATION_STEPS);
    const [currentStep, setCurrentStep] = useState(0);

    const ESTIMATED_TIME_MINUTES = 5; // Estimated 5 minutes, will show 10 (2x buffer)

    // Update step status based on progress
    useEffect(() => {
        const updateSteps = (pct) => {
            let stepIndex = 0;
            if (pct >= 5) stepIndex = 1;
            if (pct >= 15) stepIndex = 2;
            if (pct >= 88) stepIndex = 3;
            if (pct >= 95) stepIndex = 4;
            if (pct >= 100) stepIndex = 5;

            setCurrentStep(stepIndex);
            setSteps(prev => prev.map((step, idx) => ({
                ...step,
                status: idx < stepIndex ? 'complete' : idx === stepIndex ? 'running' : 'pending'
            })));
        };
        updateSteps(progress);
    }, [progress]);

    // Timer to show elapsed time and timeout warning
    useEffect(() => {
        const interval = setInterval(() => {
            const elapsed = Math.floor((Date.now() - startTime) / 1000);
            setElapsedTime(elapsed);

            // Show timeout warning after 5 minutes (300 seconds)
            if (elapsed >= 300 && !showTimeout) {
                setShowTimeout(true);
            }
        }, 1000);

        return () => clearInterval(interval);
    }, [startTime, showTimeout]);

    useEffect(() => {
        async function checkAndSetup() {
            try {
                // Check if setup is already complete
                const complete = await isSetupComplete();
                if (complete) {
                    // Auto-launch - no user interaction needed
                    onSetupComplete();
                    return;
                }

                // Run first-time setup with both progress and status callbacks
                setStatus('Starting installation...');
                setProgress(0);

                await runFirstTimeSetup(
                    (pct) => {
                        setProgress(pct);
                    },
                    (statusMsg) => {
                        setStatus(statusMsg);
                    }
                );

                // Auto-launch immediately after setup - no button required
                setStatus('✅ Installation complete! Launching app...');
                setTimeout(() => {
                    onSetupComplete();
                }, 1000);

            } catch (e) {
                console.error('Setup error:', e);
                setError(e.message || 'An error occurred during setup');
            }
        }

        checkAndSetup();
    }, [onSetupComplete]);

    const formatTime = (seconds) => {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    };

    const getStepIcon = (status) => {
        switch (status) {
            case 'complete': return '✅';
            case 'running': return '⏳';
            case 'error': return '❌';
            default: return '○';
        }
    };

    if (error) {
        // Find which step failed
        const failedStepIndex = currentStep;
        const completedSteps = steps.slice(0, failedStepIndex);

        return (
            <div className="setup-screen">
                <div className="setup-container error">
                    <h1>❌ Installation Failed</h1>

                    <div style={{ textAlign: 'left', margin: '1rem 0', padding: '1rem', background: 'rgba(0,0,0,0.3)', borderRadius: '8px' }}>
                        <p style={{ fontWeight: 'bold', marginBottom: '0.5rem' }}>Completed Steps:</p>
                        {completedSteps.map((step, idx) => (
                            <div key={idx} style={{ padding: '0.25rem 0', color: '#48bb78' }}>
                                ✅ {step.name}
                            </div>
                        ))}
                        {failedStepIndex < steps.length && (
                            <div style={{ padding: '0.25rem 0', color: '#fc8181', fontWeight: 'bold' }}>
                                ❌ {steps[failedStepIndex].name} ◄ FAILED HERE
                            </div>
                        )}
                    </div>

                    <div style={{ textAlign: 'left', margin: '1rem 0', padding: '1rem', background: 'rgba(252, 129, 129, 0.1)', border: '1px solid rgba(252, 129, 129, 0.3)', borderRadius: '8px' }}>
                        <p style={{ fontWeight: 'bold', marginBottom: '0.5rem' }}>Error Details:</p>
                        <p className="error-message" style={{ fontSize: '0.9rem', whiteSpace: 'pre-wrap' }}>{error}</p>
                    </div>

                    <div style={{ textAlign: 'left', margin: '1rem 0', padding: '1rem', background: 'rgba(66, 153, 225, 0.1)', border: '1px solid rgba(66, 153, 225, 0.3)', borderRadius: '8px' }}>
                        <p style={{ fontWeight: 'bold', marginBottom: '0.5rem' }}>💡 Suggested Fixes:</p>
                        <ul style={{ margin: '0', paddingLeft: '1.5rem', fontSize: '0.9rem' }}>
                            <li>Run the installer as Administrator</li>
                            <li>Temporarily disable antivirus software</li>
                            <li>Ensure at least 1GB of free disk space</li>
                            <li>Add SurveyScriber to antivirus exceptions</li>
                        </ul>
                    </div>

                    <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'center' }}>
                        <button onClick={() => window.location.reload()}>
                            🔄 Retry Installation
                        </button>
                        <button
                            onClick={() => navigator.clipboard.writeText(`Error at step: ${steps[failedStepIndex]?.name}\n\n${error}`)}
                            style={{ background: '#4a5568' }}
                        >
                            📋 Copy Error
                        </button>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="setup-screen">
            <div className="setup-container">
                <div className="setup-icon">🚀</div>
                <h1>Installing SurveyScriber</h1>

                {/* Estimated time display */}
                <div style={{
                    background: 'rgba(66, 153, 225, 0.1)',
                    padding: '0.75rem 1rem',
                    borderRadius: '8px',
                    marginBottom: '1rem',
                    border: '1px solid rgba(66, 153, 225, 0.3)'
                }}>
                    <p style={{ margin: 0, fontSize: '0.9rem' }}>
                        ⏱️ Estimated time: <strong>~{ESTIMATED_TIME_MINUTES * 2} minutes</strong>
                    </p>
                    <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.8rem', opacity: 0.8 }}>
                        Please wait, do not close this window
                    </p>
                </div>

                {/* Step-by-step progress */}
                <div style={{ textAlign: 'left', margin: '1rem 0' }}>
                    {steps.map((step, idx) => (
                        <div key={idx} style={{
                            padding: '0.4rem 0',
                            opacity: step.status === 'pending' ? 0.5 : 1,
                            fontWeight: step.status === 'running' ? 'bold' : 'normal'
                        }}>
                            <span style={{ marginRight: '0.5rem' }}>{getStepIcon(step.status)}</span>
                            <span style={{
                                color: step.status === 'complete' ? '#48bb78' :
                                    step.status === 'running' ? '#63b3ed' : '#a0aec0'
                            }}>
                                [{idx + 1}/{steps.length}] {step.name}
                            </span>
                        </div>
                    ))}
                </div>

                <p className="setup-status" style={{ fontStyle: 'italic' }}>{status}</p>

                <div className="progress-bar-container">
                    <div
                        className="progress-bar-fill"
                        style={{ width: `${progress}%` }}
                    />
                </div>
                <p className="progress-text">{progress}% • Elapsed: {formatTime(elapsedTime)}</p>

                {showTimeout ? (
                    <div className="timeout-warning" style={{
                        marginTop: '1.5rem',
                        padding: '1rem',
                        background: 'rgba(245, 158, 11, 0.15)',
                        border: '1px solid rgba(245, 158, 11, 0.3)',
                        borderRadius: '8px',
                        textAlign: 'left'
                    }}>
                        <p style={{ color: '#fbbf24', margin: '0 0 0.5rem 0', fontWeight: 'bold' }}>
                            ⚠️ Setup is taking longer than expected
                        </p>
                        <p style={{ fontSize: '0.9rem', margin: '0 0 0.5rem 0' }}>
                            This can happen if:
                        </p>
                        <ul style={{ fontSize: '0.85rem', margin: '0 0 1rem 1rem', paddingLeft: '0' }}>
                            <li>Antivirus is scanning the extracted files</li>
                            <li>The hard drive is slow</li>
                            <li>There's not enough disk space</li>
                        </ul>
                        <div style={{ display: 'flex', gap: '0.5rem' }}>
                            <button
                                onClick={() => window.location.reload()}
                                style={{
                                    padding: '0.5rem 1rem',
                                    background: '#f59e0b',
                                    color: 'black',
                                    border: 'none',
                                    borderRadius: '6px',
                                    cursor: 'pointer',
                                    fontWeight: 'bold'
                                }}
                            >
                                🔄 Retry Setup
                            </button>
                            <button
                                onClick={() => setShowTimeout(false)}
                                style={{
                                    padding: '0.5rem 1rem',
                                    background: '#374151',
                                    color: 'white',
                                    border: 'none',
                                    borderRadius: '6px',
                                    cursor: 'pointer'
                                }}
                            >
                                Continue Waiting
                            </button>
                        </div>
                    </div>
                ) : (
                    <p className="setup-note">
                        This only happens once. Installation will auto-complete...
                    </p>
                )}
            </div>
        </div>
    );
}

