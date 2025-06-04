/** @type {import('vite').UserConfig} */
import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
  // Load environment variables
  const env = loadEnv(mode, process.cwd(), '');

  console.log('Environment mode:', mode);
  console.log('Environment variables loaded:', Object.keys(env).filter(key => key.startsWith('VITE_')));

  return {
    // Define environment variables that should be available in the client
    define: {
      // Expose all VITE_ prefixed environment variables to the client
      ...Object.keys(env).filter(key => key.startsWith('VITE_')).reduce((acc, key) => {
        acc[`import.meta.env.${key}`] = JSON.stringify(env[key]);
        return acc;
      }, {})
    },
    // Server configuration
    "preview": {
      "allowedHosts": ["diplomacy", "archlinux"]
    },
    "dev": {
      "allowedHosts": ["diplomacy", "archlinux"]
    }
  };
});
