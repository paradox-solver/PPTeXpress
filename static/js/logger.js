let LOG_LEVEL = 'DEBUG'; // The only control switch：Change to 'INFO', 'WARN', 'ERROR' or 'SILENT' to close the corresponding log

export const logger = {
  debug: (...args) => LOG_LEVEL === 'DEBUG' && console.log('[DEBUG]', ...args),
  info: (...args) => (LOG_LEVEL === 'DEBUG' || LOG_LEVEL === 'INFO') && console.info('[INFO]', ...args),
  warn: (...args) => LOG_LEVEL !== 'ERROR' && LOG_LEVEL !== 'SILENT' && console.warn('[WARN]', ...args),
  error: (...args) => LOG_LEVEL !== 'SILENT' && console.error('[ERROR]', ...args)
};
