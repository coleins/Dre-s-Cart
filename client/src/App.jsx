import Header from "./components/Header";
import LandingPage from "./Pages/LandingPage";
import HomePage from "./Pages/HomePage";
import ContactPage from "./Pages/ContactPage";
import Help from "./Pages/Help";
import Login from "./Pages/Login";
import SignUp from "./Pages/SignUp";
import logo from "./assets/logo.png";

export default function App() {
  return (
    <div>
      <Header logo={logo} />
      <LandingPage />
      <HomePage />
      <ContactPage />
      <Help />
      <Login />
      <SignUp />
    </div>
  );
}
