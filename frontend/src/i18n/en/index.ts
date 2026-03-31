import auth from "./auth";
import common from "./common";
import console from "./console";
import landing from "./landing";

export default {
  ...common,
  auth,
  landing,
  ...console,
};
