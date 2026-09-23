import { createCatppuccinPlugin } from '@catppuccin/daisyui';

import { getCatppuccinDaisyOptions } from './site-theme';

export default createCatppuccinPlugin('mocha', {}, getCatppuccinDaisyOptions('mocha'));
