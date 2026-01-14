import axios from 'axios';
import * as Popper from '@popperjs/core';
import * as bootstrap from 'bootstrap';

window.axios = axios;
window.Popper = Popper;
window.bootstrap = bootstrap;

window.axios.defaults.headers.common['X-Requested-With'] = 'XMLHttpRequest';
