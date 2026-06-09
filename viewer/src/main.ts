import { App } from './components/App';
import './styles.css';

const root = document.querySelector<HTMLElement>('#app');
if (!root) throw new Error('Missing #app root.');

void new App(root).start();
