import React from "react";
import PropTypes from "prop-types";

/**
 * A simple bottom sheet that slides up from the bottom of the screen,
 * showing the current phase summary.
 */
export function PhaseSummaryBottomSheet({ phase, summaryText, onClose }) {

  return (
    <div style={{
      position: 'fixed',
      bottom: 0,
      left: 0,
      width: '100%',
      maxHeight: '40%',
      backgroundColor: '#fff',
      boxShadow: '0 -2px 8px rgba(0,0,0,0.25)',
      zIndex: 9999,
      overflowY: 'auto',
      transition: 'transform 0.3s ease-in-out',
      transform: 'translateY(0%)'
    }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '0.5rem',
        background: '#f2f2f2',
        borderBottom: '1px solid #ccc'
      }}>
        <h5 className="mb-0">Summary for {phase}:</h5>
        <button className="btn btn-sm btn-danger" onClick={onClose}>Close</button>
      </div>
      <div style={{
        padding: '1rem',
        overflowY: 'auto'
      }}>
        {summaryText || "No phase summary available."}
      </div>
    </div>
  );
}

PhaseSummaryBottomSheet.propTypes = {
  phase: PropTypes.string,
  summaryText: PropTypes.string,
  onClose: PropTypes.func.isRequired
};